import cv2
import numpy as np
import os
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def train_model(dataset_path='dataset', model_path='model.yml', labels_path='labels.json'):
    """
    Enhanced training with better preprocessing and data augmentation.
    Structure: dataset_path/User_Name/1.jpg, 2.jpg, ...
    """
    
    if not os.path.exists(dataset_path):
        logging.error(f"Dataset directory '{dataset_path}' not found.")
        return

    # Load cascades
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)
    
    if face_cascade.empty():
        logging.error("Failed to load Haar Cascade classifier.")
        return
    
    # Alternative cascade for better detection
    cascade_alt_path = cv2.data.haarcascades + 'haarcascade_frontalface_alt2.xml'
    face_cascade_alt = cv2.CascadeClassifier(cascade_alt_path)

    # Initialize LBPH Face Recognizer with optimized parameters
    # radius=2, neighbors=8, grid_x=8, grid_y=8 are good defaults
    recognizer = cv2.face.LBPHFaceRecognizer_create(
        radius=2,
        neighbors=8,
        grid_x=8,
        grid_y=8
    )

    faces = []
    ids = []
    label_map = {}
    current_id = 0

    logging.info("Starting enhanced training process...")

    # Iterate through all user directories
    for root, dirs, files in os.walk(dataset_path):
        image_files = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        
        if not image_files:
            continue
        
        label = os.path.basename(root).replace(" ", "_").lower()
        
        # Skip if it's the root dataset directory
        if root == dataset_path:
            continue
        
        # Assign ID to label if new
        if label not in label_map:
            label_map[label] = current_id
            logging.info(f"Assigned ID {current_id} to label '{label}'")
            current_id += 1
        
        label_id = label_map[label]
        user_face_count = 0

        for file in image_files:
            path = os.path.join(root, file)
            
            try:
                # Read image in color first
                img_color = cv2.imread(path, cv2.IMREAD_COLOR)
                if img_color is None:
                    logging.warning(f"Could not read image: {path}")
                    continue
                
                # Convert to grayscale
                img = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)
                
                # Apply CLAHE for better contrast
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                img = clahe.apply(img)
                
                # Try multiple detection strategies
                detected_faces = face_cascade.detectMultiScale(
                    img, 
                    scaleFactor=1.1, 
                    minNeighbors=4,
                    minSize=(30, 30)
                )
                
                # If no face found, try alternative cascade
                if len(detected_faces) == 0 and not face_cascade_alt.empty():
                    detected_faces = face_cascade_alt.detectMultiScale(
                        img,
                        scaleFactor=1.1,
                        minNeighbors=3,
                        minSize=(30, 30)
                    )
                
                if len(detected_faces) == 0:
                    logging.warning(f"No face detected in: {path}")
                    continue
                
                # Process each detected face
                for (x, y, w, h) in detected_faces:
                    # Extract face ROI
                    roi = img[y:y+h, x:x+w]
                    
                    # Resize to uniform size
                    roi_resized = cv2.resize(roi, (200, 200))
                    
                    # Apply histogram equalization
                    roi_equalized = cv2.equalizeHist(roi_resized)
                    
                    # Add original processed face
                    faces.append(roi_equalized)
                    ids.append(label_id)
                    user_face_count += 1
                    
                    # Data augmentation: slight brightness variations
                    # This helps the model generalize better to different lighting
                    for brightness_delta in [-30, 30]:
                        roi_bright = cv2.convertScaleAbs(roi_resized, alpha=1.0, beta=brightness_delta)
                        roi_bright = cv2.equalizeHist(roi_bright)
                        faces.append(roi_bright)
                        ids.append(label_id)
                        user_face_count += 1
                    
                    # Data augmentation: horizontal flip
                    # Helps with slight angle variations
                    roi_flip = cv2.flip(roi_equalized, 1)
                    faces.append(roi_flip)
                    ids.append(label_id)
                    user_face_count += 1
                    
                    # Only use first face if multiple detected in training image
                    break
                    
            except Exception as e:
                logging.error(f"Error processing {path}: {e}")

        if user_face_count > 0:
            logging.info(f"Collected {user_face_count} training samples for '{label}' (ID: {label_id})")

    if not faces:
        logging.warning("No faces found in the dataset. Model not trained.")
        return

    # Train the model
    logging.info(f"Training on {len(faces)} face samples (including augmented data) for {len(label_map)} subjects...")
    recognizer.train(faces, np.array(ids))

    # Save the model
    recognizer.save(model_path)
    logging.info(f"Model saved to {model_path}")

    # Save the label mapping (ID -> Name)
    id_to_name = {v: k for k, v in label_map.items()}
    with open(labels_path, 'w') as f:
        json.dump(id_to_name, f, indent=2)
    logging.info(f"Labels saved to {labels_path}")
    
    # Print training summary
    logging.info("=" * 60)
    logging.info("TRAINING SUMMARY")
    logging.info("=" * 60)
    logging.info(f"Total subjects: {len(label_map)}")
    logging.info(f"Total training samples: {len(faces)}")
    logging.info(f"Average samples per subject: {len(faces) / len(label_map):.1f}")
    logging.info("Label mapping:")
    for label_id, name in sorted(id_to_name.items()):
        count = ids.count(label_id)
        logging.info(f"  ID {label_id}: {name} ({count} samples)")
    logging.info("=" * 60)

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_dir = os.path.join(base_dir, 'dataset')
    model_file = os.path.join(base_dir, 'model.yml')
    labels_file = os.path.join(base_dir, 'labels.json')

    train_model(dataset_dir, model_file, labels_file)