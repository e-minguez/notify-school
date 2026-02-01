import os
import sys
import subprocess
import requests
import time
from dotenv import load_dotenv

# Load configuration
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    sys.stderr.write("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in .env\n")
    sys.exit(1)

# Tracking for duplicate prevention
last_sent_time = 0
last_sent_signature = ""

def send_telegram(sender, subject):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    # Plain text format to prevent Markdown parsing errors
    text = f"School Email Alert\n\nFrom: {sender}\nSubject: {subject}"
    
    try:
        response = requests.post(url, data={"chat_id": CHAT_ID, "text": text})
        if response.status_code != 200:
            sys.stderr.write(f"Telegram Error {response.status_code}: {response.text}\n")
    except Exception as e:
        sys.stderr.write(f"Connection Failed: {e}\n")

def main():
    global last_sent_time, last_sent_signature
    
    # Run dbus-monitor
    cmd = ["dbus-monitor", "interface='org.freedesktop.Notifications'"]
    # We use line buffering (bufsize=1) to ensure immediate processing
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

    capture_mode = False
    line_count = 0
    current_app = ""
    current_sender = ""
    current_subject = ""

    try:
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            
            if "member=Notify" in line:
                capture_mode = True
                line_count = 0
                current_app = ""
                current_sender = ""
                current_subject = ""
                continue

            if capture_mode:
                line_count += 1
                
                # Line 1: App Name
                if line_count == 1 and "string" in line:
                    parts = line.split('"')
                    if len(parts) > 1: current_app = parts[1]
                
                # Line 4: Sender
                elif line_count == 4 and "string" in line:
                    parts = line.split('"')
                    if len(parts) > 1: current_sender = parts[1]

                # Line 5: Subject
                elif line_count == 5 and "string" in line:
                    # Safely extract text between first and last quote
                    first = line.find('"')
                    last = line.rfind('"')
                    if first != -1 and last != -1:
                        current_subject = line[first+1:last]
                    
                    # Check Logic
                    if "Firefox" in current_app:
                        signature = f"{current_sender}|{current_subject}"
                        now = time.time()
                        
                        # Debounce (5 seconds)
                        if signature != last_sent_signature or (now - last_sent_time) > 5:
                            send_telegram(current_sender, current_subject)
                            last_sent_time = now
                            last_sent_signature = signature
                    
                    capture_mode = False

    except KeyboardInterrupt:
        pass
    except Exception as e:
        sys.stderr.write(f"Fatal Error: {e}\n")
    finally:
        process.kill()

if __name__ == "__main__":
    main()
