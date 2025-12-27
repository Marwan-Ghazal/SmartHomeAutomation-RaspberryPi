how to run the project 

1) Make sure Mosquitto broker is running
bash
sudo systemctl status mosquitto
2) Start Peripheral app (on Peripheral Pi)
bash
python3 peripheral_pi/main.py
3) Start Master gateway app (on Master Pi)
bash
python3 master_pi/main.py
4) Start the web server (on Master Pi, separate terminal)
bash
python3 web/server.py