import cv2
import numpy as np
import os
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class FaceEngine:
    def __init__(self, model_path='model.yml', labels_path='labels.json'):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_full_path = os.path.join(self.base_dir, model_path)
        self.labels_full_path = os.path.join(self.base_dir, labels_path)
        
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.face_cascade = None
        self.face_cascade_alt = None  # Backup cascade
        self.labels = {}
        self.model_loaded = False

        self.load_resources()

    def load_resources(self):
        """Loads the trained model and labels with multiple cascade classifiers."""
        # Load primary Haar Cascade
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        if self.face_cascade.empty():
            logging.critical("Failed to load primary Haar Cascade classifier.")
            return
        
        # Load alternative cascade for better detection
        cascade_alt_path = cv2.data.haarcascades + 'haarcascade_frontalface_alt2.xml'
        self.face_cascade_alt = cv2.CascadeClassifier(cascade_alt_path)
        if self.face_cascade_alt.empty():
            logging.warning("Failed to load alternative Haar Cascade classifier.")
            self.face_cascade_alt = None

        # Load ID labels
        if os.path.exists(self.labels_full_path):
            try:
                with open(self.labels_full_path, 'r') as f:
                    start_map = json.load(f)
                    self.labels = {int(k): v for k, v in start_map.items()}
            except Exception as e:
                logging.error(f"Error loading labels: {e}")
                return
        else:
            logging.warning(f"Labels file not found at {self.labels_full_path}")
            return

        # Load Model
        if os.path.exists(self.model_full_path):
            try:
                self.recognizer.read(self.model_full_path)
                self.model_loaded = True
                logging.info("Face recognition model loaded successfully.")
            except Exception as e:
                logging.error(f"Error loading model: {e}")
        else:
            logging.warning(f"Model file not found at {self.model_full_path}")

    def preprocess_image(self, img):
        """Enhanced image preprocessing for better face detection."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # This works better than simple histogram equalization for varying lighting
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Optional: Apply bilateral filter to reduce noise while preserving edges
        denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
        
        return denoised

    def detect_faces_multi_scale(self, gray):
        """
        Try multiple detection strategies to improve reliability.
        Returns the best set of detected faces.
        """
        all_detections = []
        
        # Strategy 1: Standard detection (balanced)
        faces1 = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=4,  # Reduced from 5 for better sensitivity
            minSize=(50, 50),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        if len(faces1) > 0:
            all_detections.append(('standard', faces1))
        
        # Strategy 2: More sensitive detection (lower minNeighbors)
        faces2 = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.05,  # Smaller scale factor = more thorough
            minNeighbors=3,
            minSize=(40, 40),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        if len(faces2) > 0:
            all_detections.append(('sensitive', faces2))
        
        # Strategy 3: Alternative cascade if available
        if self.face_cascade_alt is not None:
            faces3 = self.face_cascade_alt.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=3,
                minSize=(50, 50),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            if len(faces3) > 0:
                all_detections.append(('alternative', faces3))
        
        # Strategy 4: Try with smaller minimum size for distant faces
        faces4 = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.2,
            minNeighbors=3,
            minSize=(30, 30),
            maxSize=(400, 400),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        if len(faces4) > 0:
            all_detections.append(('wide_range', faces4))
        
        if not all_detections:
            return np.array([])
        
        # Merge overlapping detections using NMS (Non-Maximum Suppression)
        merged_faces = self.merge_detections([faces for _, faces in all_detections])
        
        logging.info(f"Detection strategies found: {[(name, len(faces)) for name, faces in all_detections]}")
        logging.info(f"After merging: {len(merged_faces)} unique face(s)")
        
        return merged_faces

    def merge_detections(self, detection_lists):
        """
        Merge overlapping face detections using Non-Maximum Suppression.
        """
        if not detection_lists:
            return np.array([])
        
        # Combine all detections
        all_boxes = np.vstack(detection_lists)
        
        if len(all_boxes) == 0:
            return np.array([])
        
        # Apply NMS
        boxes = []
        scores = []
        for i, (x, y, w, h) in enumerate(all_boxes):
            boxes.append([x, y, x + w, y + h])
            # Assign score based on box size (larger faces = higher confidence)
            scores.append(w * h)
        
        boxes = np.array(boxes)
        scores = np.array(scores)
        
        # Simple NMS implementation
        picked = []
        indices = np.argsort(scores)[::-1]
        
        while len(indices) > 0:
            current = indices[0]
            picked.append(current)
            
            if len(indices) == 1:
                break
            
            # Calculate IoU with remaining boxes
            current_box = boxes[current]
            remaining_boxes = boxes[indices[1:]]
            
            # Calculate intersection
            xx1 = np.maximum(current_box[0], remaining_boxes[:, 0])
            yy1 = np.maximum(current_box[1], remaining_boxes[:, 1])
            xx2 = np.minimum(current_box[2], remaining_boxes[:, 2])
            yy2 = np.minimum(current_box[3], remaining_boxes[:, 3])
            
            w = np.maximum(0, xx2 - xx1)
            h = np.maximum(0, yy2 - yy1)
            intersection = w * h
            
            # Calculate union
            current_area = (current_box[2] - current_box[0]) * (current_box[3] - current_box[1])
            remaining_areas = (remaining_boxes[:, 2] - remaining_boxes[:, 0]) * \
                            (remaining_boxes[:, 3] - remaining_boxes[:, 1])
            union = current_area + remaining_areas - intersection
            
            # IoU
            iou = intersection / union
            
            # Keep boxes with IoU < 0.5
            indices = indices[1:][iou < 0.5]
        
        # Convert back to (x, y, w, h) format
        result = []
        for idx in picked:
            x1, y1, x2, y2 = boxes[idx]
            result.append([int(x1), int(y1), int(x2 - x1), int(y2 - y1)])
        
        return np.array(result)

    def select_best_face(self, faces, img_shape):
        """
        Select the best face from multiple detections.
        Prioritizes: centered, larger, and closer to standard face proportions.
        """
        if len(faces) == 0:
            return None
        
        if len(faces) == 1:
            return faces[0]
        
        img_height, img_width = img_shape[:2]
        img_center_x, img_center_y = img_width // 2, img_height // 2
        
        scores = []
        for (x, y, w, h) in faces:
            # Calculate face center
            face_center_x = x + w // 2
            face_center_y = y + h // 2
            
            # Distance from image center (normalized)
            dist_from_center = np.sqrt(
                ((face_center_x - img_center_x) / img_width) ** 2 +
                ((face_center_y - img_center_y) / img_height) ** 2
            )
            
            # Size score (larger is better, normalized)
            size_score = (w * h) / (img_width * img_height)
            
            # Aspect ratio score (closer to 1.0 is better for faces)
            aspect_ratio = w / h if h > 0 else 0
            aspect_score = 1.0 - abs(aspect_ratio - 1.0)
            
            # Combined score (lower is better for distance, higher for others)
            score = (1.0 - dist_from_center) * 0.4 + size_score * 0.4 + aspect_score * 0.2
            scores.append(score)
        
        best_idx = np.argmax(scores)
        logging.info(f"Selected face {best_idx} from {len(faces)} candidates (score: {scores[best_idx]:.3f})")
        return faces[best_idx]

    def verify_face(self, image_bytes) -> tuple[bool, str | None]:
        """
        Enhanced face verification with improved detection and preprocessing.
        Returns (True, name) if authorized, else (False, None).
        """
        if not self.model_loaded:
            logging.error("Model not loaded. Access denied.")
            return False, None

        try:
            # Decode image
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                logging.error("Failed to decode image.")
                return False, None

            # Enhanced preprocessing
            gray = self.preprocess_image(img)
            
            # Multi-strategy face detection
            faces = self.detect_faces_multi_scale(gray)

            face_count = len(faces)
            if face_count == 0:
                logging.info("No face detected after trying multiple strategies.")
                return False, None
            
            # Select best face if multiple detected
            if face_count > 1:
                logging.warning(f"Multiple faces detected ({face_count}). Selecting best candidate.")
                face = self.select_best_face(faces, img.shape)
                if face is None:
                    return False, None
                x, y, w, h = face
            else:
                x, y, w, h = faces[0]
            
            # Extract and prepare ROI
            roi_gray = gray[y:y+h, x:x+w]
            
            # Resize for consistency with training
            roi_gray = cv2.resize(roi_gray, (200, 200))
            
            # Additional preprocessing for recognition
            roi_gray = cv2.equalizeHist(roi_gray)

            # Predict
            label_id, confidence = self.recognizer.predict(roi_gray)

            # Adjusted threshold for better accuracy
            # Lower = stricter (use 50-60 for high security)
            # Higher = more lenient (use 80-90 for convenience)
            STRICT_THRESHOLD = 110

            logging.info(f"Face predicted: ID={label_id}, Confidence={confidence:.2f}, Threshold={STRICT_THRESHOLD}")

            if confidence < STRICT_THRESHOLD:
                name = self.labels.get(label_id, "Unknown")
                logging.info(f"Access GRANTED for {name} (confidence: {confidence:.2f})")
                return True, name
            else:
                logging.info(f"Access DENIED. Confidence {confidence:.2f} above threshold {STRICT_THRESHOLD}")
                return False, None

        except Exception as e:
            logging.error(f"Exception during verification: {e}", exc_info=True)
            return False, None

# Singleton instance
engine = FaceEngine()

if __name__ == "__main__":
    import sys
    print("--- Enhanced Face Engine Standalone Test ---")
    if engine.model_loaded:
        print(f"Model loaded successfully. Labels: {engine.labels}")
    else:
        print("Model NOT loaded. Please run train_faces.py with a populated dataset first.")
    
    if len(sys.argv) > 1:
        test_path = sys.argv[1]
        print(f"Testing image: {test_path}")
        if os.path.exists(test_path):
            with open(test_path, 'rb') as f:
                img_bytes = f.read()
            authorized, name = engine.verify_face(img_bytes)
            print(f"Result: Authorized={authorized}, Name={name}")
        else:
            print("File not found.")