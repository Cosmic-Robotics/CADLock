import os
import json
import sys
import time
import threading
from datetime import datetime
import psutil
import pystray
from PIL import Image, ImageDraw

# Simple version - easier to debug
class SimpleCADTray:
    def __init__(self):
        self.user = os.getenv('USERNAME')
        self.computer = os.getenv('COMPUTERNAME')
        self.lock_dir = r"G:\Shared drives\Cosmic\Engineering\50 - CAD Data\Locks"
        self.cad_root = r"G:\Shared drives\Cosmic\Engineering\50 - CAD Data"
        
        self.monitor_running = False
        self.monitor_thread = None
        self.log_entries = []
        
        # Ensure directories exist
        os.makedirs(self.lock_dir, exist_ok=True)
        
        print(f"SimpleCADTray initialized for user: {self.user}")
    
    def create_simple_icon(self, lock_count=0):
        """Create a very simple icon"""
        # Create a simple 32x32 icon
        image = Image.new('RGBA', (32, 32), (70, 130, 180, 255))  # Blue background
        draw = ImageDraw.Draw(image)
        
        # White border
        draw.rectangle([0, 0, 31, 31], outline=(255, 255, 255, 255), width=2)
        
        # Draw "L" in center
        draw.rectangle([8, 8, 12, 24], fill=(255, 255, 255, 255))  # Vertical line
        draw.rectangle([8, 20, 20, 24], fill=(255, 255, 255, 255))  # Horizontal line
        
        # Add counter if > 0
        if lock_count > 0:
            # Red circle in corner
            draw.ellipse([20, 2, 30, 12], fill=(255, 0, 0, 255))
            # White number
            count_str = str(min(lock_count, 9))  # Single digit only
            draw.text((23, 4), count_str, fill=(255, 255, 255, 255))
        
        return image
    
    def get_my_lock_count(self):
        """Count my locks"""
        count = 0
        try:
            if os.path.exists(self.lock_dir):
                for lock_file in os.listdir(self.lock_dir):
                    if lock_file.endswith('.lock'):
                        lock_path = os.path.join(self.lock_dir, lock_file)
                        try:
                            with open(lock_path, 'r') as f:
                                lock_data = json.load(f)
                            if lock_data.get('user') == self.user:
                                count += 1
                        except:
                            continue
        except:
            pass
        return count
    
    def log_message(self, message):
        """Simple logging"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.log_entries.append(log_entry)
        
        # Keep only last 50 entries
        if len(self.log_entries) > 50:
            self.log_entries = self.log_entries[-50:]
        
        print(log_entry)  # Also print to console when visible
    
    def show_logs(self, icon=None, item=None):
        """Show logs in notepad"""
        try:
            import tempfile
            import subprocess
            
            # Create temporary file with logs
            log_content = "\n".join(self.log_entries[-20:])  # Last 20 entries
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(f"CAD Lock Monitor Logs\n")
                f.write(f"User: {self.user}\n")
                f.write(f"Status: {'MONITORING' if self.monitor_running else 'STOPPED'}\n")
                f.write(f"Lock Count: {self.get_my_lock_count()}\n")
                f.write("=" * 40 + "\n\n")
                f.write(log_content)
                temp_file = f.name
            
            # Open in notepad
            subprocess.Popen(['notepad', temp_file])
            
            # Clean up after 2 minutes
            threading.Timer(120.0, lambda: os.unlink(temp_file) if os.path.exists(temp_file) else None).start()
            
        except Exception as e:
            print(f"Error showing logs: {e}")
    
    def is_solidworks_running(self):
        """Check if SolidWorks is running"""
        for proc in psutil.process_iter(['name']):
            try:
                if 'sldworks' in proc.info['name'].lower():
                    return True
            except:
                continue
        return False
    
    def find_open_files(self):
        """Find open SolidWorks files by detecting temp files"""
        open_files = set()
        temp_files_found = []
        
        try:
            # Walk through the CAD directory looking for SolidWorks temp files
            for root, dirs, files in os.walk(self.cad_root):
                for file in files:
                    # SolidWorks creates temp files with ~$ prefix when files are open
                    if file.startswith('~$'):
                        temp_files_found.append(os.path.join(root, file))
                        
                        if file.lower().endswith(('.sldprt', '.sldasm', '.slddrw')):
                            # Remove the ~$ prefix to get the original filename
                            original_file = file[2:]
                            original_path = os.path.join(root, original_file)
                            
                            # Only include if the original file actually exists
                            if os.path.exists(original_path):
                                open_files.add(original_path)
            
            # Debug logging
            if temp_files_found:
                self.log_message(f"Found {len(temp_files_found)} temp files:")
                for temp_file in temp_files_found:
                    self.log_message(f"  Temp file: {temp_file}")
            else:
                self.log_message("No temp files found in CAD directory")
                            
        except Exception as e:
            self.log_message(f"Error scanning for open files: {e}")
            
        return open_files
    
    def create_lock(self, file_path):
        """Create lock file"""
        try:
            # Simple lock path generation
            rel_path = os.path.relpath(file_path, self.cad_root)
            safe_path = rel_path.replace('\\', '_').replace('/', '_').replace(':', '_')
            safe_path = safe_path.replace('*', '_').replace('?', '_').replace('"', '_')
            lock_filename = f"{safe_path}.lock"
            lock_path = os.path.join(self.lock_dir, lock_filename)
            
            # Check if already exists and is ours
            if os.path.exists(lock_path):
                with open(lock_path, 'r') as f:
                    lock_data = json.load(f)
                if lock_data.get('user') == self.user:
                    return True  # Already our lock
                else:
                    return False  # Someone else's lock
            
            # Create new lock
            lock_data = {
                'user': self.user,
                'computer': self.computer,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'file': os.path.basename(file_path),
                'original_path': file_path,
                'auto_created': True
            }
            
            with open(lock_path, 'w') as f:
                json.dump(lock_data, f, indent=2)
            
            self.log_message(f"LOCKED: {os.path.basename(file_path)}")
            return True
            
        except Exception as e:
            self.log_message(f"Error creating lock: {e}")
            return False
    
    def remove_lock(self, file_path):
        """Remove lock file"""
        try:
            rel_path = os.path.relpath(file_path, self.cad_root)
            safe_path = rel_path.replace('\\', '_').replace('/', '_').replace(':', '_')
            safe_path = safe_path.replace('*', '_').replace('?', '_').replace('"', '_')
            lock_filename = f"{safe_path}.lock"
            lock_path = os.path.join(self.lock_dir, lock_filename)
            
            if os.path.exists(lock_path):
                with open(lock_path, 'r') as f:
                    lock_data = json.load(f)
                
                if lock_data.get('user') == self.user and lock_data.get('auto_created'):
                    os.remove(lock_path)
                    self.log_message(f"UNLOCKED: {os.path.basename(file_path)}")
                    return True
            return False
            
        except Exception as e:
            self.log_message(f"Error removing lock: {e}")
            return False
    
    def cleanup_my_locks(self):
        """Remove all auto-created locks by current user"""
        removed = 0
        try:
            if os.path.exists(self.lock_dir):
                for lock_file in os.listdir(self.lock_dir):
                    if lock_file.endswith('.lock'):
                        lock_path = os.path.join(self.lock_dir, lock_file)
                        try:
                            with open(lock_path, 'r') as f:
                                lock_data = json.load(f)
                            
                            if (lock_data.get('user') == self.user and 
                                lock_data.get('auto_created')):
                                os.remove(lock_path)
                                removed += 1
                        except:
                            continue
        except:
            pass
        
        if removed > 0:
            self.log_message(f"CLEANUP: Removed {removed} locks")
        return removed
    
    def monitor_loop(self):
        """Main monitoring loop"""
        self.log_message("Monitor started")
        
        while self.monitor_running:
            try:
                sw_running = self.is_solidworks_running()
                self.log_message(f"SolidWorks running: {sw_running}")
                
                if sw_running:
                    # Get currently open files
                    open_files = self.find_open_files()
                    self.log_message(f"Found {len(open_files)} open files")
                    
                    # Log the open files for debugging
                    for file_path in open_files:
                        self.log_message(f"Open file: {os.path.basename(file_path)}")
                    
                    # Create locks for open files
                    for file_path in open_files:
                        # Check if lock already exists before creating
                        rel_path = os.path.relpath(file_path, self.cad_root)
                        safe_path = rel_path.replace('\\', '_').replace('/', '_').replace(':', '_')
                        safe_path = safe_path.replace('*', '_').replace('?', '_').replace('"', '_')
                        lock_filename = f"{safe_path}.lock"
                        lock_path = os.path.join(self.lock_dir, lock_filename)
                        
                        if not os.path.exists(lock_path):
                            # Create new auto lock
                            lock_data = {
                                'user': self.user,
                                'computer': self.computer,
                                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'file': os.path.basename(file_path),
                                'original_path': file_path,
                                'auto_created': True  # Make sure this is set to True
                            }
                            
                            with open(lock_path, 'w') as f:
                                json.dump(lock_data, f, indent=2)
                            
                            self.log_message(f"LOCKED: {os.path.basename(file_path)} (auto)")
                        else:
                            # Update existing lock to mark it as auto-created
                            try:
                                with open(lock_path, 'r') as f:
                                    lock_data = json.load(f)
                                
                                if lock_data.get('user') == self.user:
                                    lock_data['auto_created'] = True
                                    lock_data['last_seen'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    
                                    with open(lock_path, 'w') as f:
                                        json.dump(lock_data, f, indent=2)
                                    
                                    self.log_message(f"Updated lock to auto: {os.path.basename(file_path)}")
                            except Exception as e:
                                self.log_message(f"Error updating lock: {e}")
                    
                    # Remove locks for files that are no longer open
                    try:
                        removed_any = False
                        if os.path.exists(self.lock_dir):
                            for lock_file in os.listdir(self.lock_dir):
                                if lock_file.endswith('.lock'):
                                    lock_path = os.path.join(self.lock_dir, lock_file)
                                    try:
                                        with open(lock_path, 'r') as f:
                                            lock_data = json.load(f)
                                        
                                        # Only process our auto-created locks
                                        if (lock_data.get('user') == self.user and 
                                            lock_data.get('auto_created')):
                                            original_path = lock_data.get('original_path')
                                            
                                            if original_path:
                                                # Check if this file is still open
                                                if original_path not in open_files:
                                                    # File is no longer open, remove the lock
                                                    os.remove(lock_path)
                                                    self.log_message(f"UNLOCKED: {os.path.basename(original_path)}")
                                                    removed_any = True
                                    except Exception as e:
                                        # If we can't read the lock file, skip it
                                        self.log_message(f"Error reading lock file {lock_file}: {e}")
                                        continue
                        
                        if not removed_any and len(open_files) == 0:
                            # No open files but we might have locks - remove them all
                            my_locks = self.get_my_lock_count()
                            if my_locks > 0:
                                self.log_message(f"No open files detected but {my_locks} locks remain - removing all auto-locks...")
                                # Remove all our auto-created locks since no files are open
                                if os.path.exists(self.lock_dir):
                                    for lock_file in os.listdir(self.lock_dir):
                                        if lock_file.endswith('.lock'):
                                            lock_path = os.path.join(self.lock_dir, lock_file)
                                            self.log_message(f"Checking lock file: {lock_file}")
                                            try:
                                                with open(lock_path, 'r') as f:
                                                    lock_data = json.load(f)
                                                
                                                self.log_message(f"Lock data - User: {lock_data.get('user')}, Auto: {lock_data.get('auto_created')}")
                                                
                                                if (lock_data.get('user') == self.user and 
                                                    lock_data.get('auto_created')):
                                                    self.log_message(f"Attempting to remove: {lock_path}")
                                                    os.remove(lock_path)
                                                    self.log_message(f"UNLOCKED: {lock_data.get('file', 'unknown')} (no temp file)")
                                                    removed_any = True
                                                else:
                                                    self.log_message(f"Skipping lock - User: {lock_data.get('user')} (me: {self.user}), Auto: {lock_data.get('auto_created')}")
                                                    
                                            except Exception as e:
                                                self.log_message(f"Error processing lock {lock_file}: {e}")
                                                continue
                                            
                    except Exception as e:
                        self.log_message(f"Error during cleanup: {e}")
                        
                else:
                    # SolidWorks not running - cleanup all our auto-locks
                    removed = self.cleanup_my_locks()
                    if removed > 0:
                        self.log_message(f"CLEANUP: SolidWorks closed - removed {removed} locks")
                
                # Update icon with current counts
                self.update_icon()
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                self.log_message(f"Monitor error: {e}")
                time.sleep(5)
        
        self.log_message("Monitor stopped")
    
    def update_icon(self):
        """Update tray icon"""
        try:
            if hasattr(self, 'tray_icon') and self.tray_icon:
                lock_count = self.get_my_lock_count()
                self.tray_icon.icon = self.create_simple_icon(lock_count)
                self.tray_icon.title = f"CAD Locks: {lock_count} files"
        except Exception as e:
            print(f"Error updating icon: {e}")
    
    def start_monitoring(self, icon=None, item=None):
        """Start monitoring"""
        if not self.monitor_running:
            self.monitor_running = True
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()
            self.log_message("Monitoring started")
            self.update_icon()
    
    def stop_monitoring(self, icon=None, item=None):
        """Stop monitoring"""
        if self.monitor_running:
            self.monitor_running = False
            self.cleanup_my_locks()
            self.log_message("Monitoring stopped")
            self.update_icon()
    
    def unlock_all(self, icon=None, item=None):
        """Unlock all my files"""
        removed = self.cleanup_my_locks()
        self.update_icon()
    
    def quit_app(self, icon=None, item=None):
        """Quit application"""
        self.log_message("Shutting down...")
        self.stop_monitoring()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
    
    def run(self):
        """Run the tray application"""
        print("Creating system tray icon...")
        
        # Create menu
        menu = pystray.Menu(
            pystray.MenuItem("Show Logs", self.show_logs),
            pystray.MenuItem("Start Monitor", self.start_monitoring, 
                           enabled=lambda item: not self.monitor_running),
            pystray.MenuItem("Stop Monitor", self.stop_monitoring, 
                           enabled=lambda item: self.monitor_running),
            pystray.MenuItem("Unlock All", self.unlock_all),
            pystray.MenuItem("Quit", self.quit_app)
        )
        
        # Create tray icon
        self.tray_icon = pystray.Icon(
            "CAD Lock Monitor",
            self.create_simple_icon(0),
            "CAD Lock Monitor",
            menu
        )
        
        # Auto-start monitoring
        self.start_monitoring()
        
        print("Starting tray icon...")
        try:
            # This should make the icon appear
            self.tray_icon.run()
        except Exception as e:
            print(f"Error running tray icon: {e}")
            self.log_message(f"Tray error: {e}")

def main():
    print("=== CAD Lock Simple Tray Monitor ===")
    print("Starting up...")
    
    try:
        app = SimpleCADTray()
        app.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()