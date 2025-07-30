import os
import json
import time
import psutil
import threading
from datetime import datetime
from pathlib import Path
import win32gui
import win32process
import win32api
from collections import defaultdict

class AutoLockMonitor:
    def __init__(self):
        self.lock_dir = r"G:\Shared drives\Cosmic\Engineering\50 - CAD Data\Locks"
        self.cad_root = r"G:\Shared drives\Cosmic\Engineering\50 - CAD Data"
        self.user = os.getenv('USERNAME')
        self.computer = os.getenv('COMPUTERNAME')
        self.running = False
        self.current_locks = set()
        self.monitor_thread = None
        
        # Create lock directory if it doesn't exist
        os.makedirs(self.lock_dir, exist_ok=True)
    
    def get_open_solidworks_files(self):
        """Get list of files currently open in SolidWorks"""
        open_files = set()
        
        try:
            # Method 1: Check SolidWorks processes and their open file handles
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    if proc.info['name'] and 'sldworks' in proc.info['name'].lower():
                        # Get open files for this SolidWorks process
                        process = psutil.Process(proc.info['pid'])
                        for file_handle in process.open_files():
                            file_path = file_handle.path
                            if any(file_path.lower().endswith(ext) for ext in ['.sldprt', '.sldasm', '.slddrw']):
                                # Only track files in our CAD directory
                                if file_path.startswith(self.cad_root):
                                    open_files.add(file_path)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            # Method 2: Check SolidWorks window titles for additional files
            solidworks_files = self.get_files_from_window_titles()
            open_files.update(solidworks_files)
            
        except Exception as e:
            print(f"Error detecting open files: {e}")
        
        return open_files
    
    def get_files_from_window_titles(self):
        """Extract file names from SolidWorks window titles"""
        open_files = set()
        
        def enum_windows_callback(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                class_name = win32gui.GetClassName(hwnd)
                
                # Check if it's a SolidWorks window
                if ('solidworks' in class_name.lower() or 
                    'sldworks' in window_title.lower() or
                    any(ext in window_title.lower() for ext in ['.sldprt', '.sldasm', '.slddrw'])):
                    
                    # Extract file path from window title
                    # SolidWorks titles often contain the full path
                    for ext in ['.sldprt', '.sldasm', '.slddrw']:
                        if ext in window_title.lower():
                            # Try to extract the full path
                            try:
                                # Look for common patterns in SolidWorks window titles
                                if ' - ' in window_title:
                                    potential_path = window_title.split(' - ')[0]
                                    if os.path.exists(potential_path) and potential_path.startswith(self.cad_root):
                                        open_files.add(potential_path)
                                
                                # Also check if the title contains just the filename
                                if ext in window_title.lower():
                                    filename = window_title.split(' - ')[0] if ' - ' in window_title else window_title
                                    # Search for this file in the CAD directory
                                    found_files = self.find_file_in_cad_directory(filename)
                                    open_files.update(found_files)
                            except:
                                pass
        
        try:
            win32gui.EnumWindows(enum_windows_callback, None)
        except Exception as e:
            print(f"Error enumerating windows: {e}")
        
        return open_files
    
    def find_file_in_cad_directory(self, filename):
        """Find file by name in CAD directory structure"""
        found_files = []
        
        # Clean up filename
        filename = filename.strip()
        if not any(filename.lower().endswith(ext) for ext in ['.sldprt', '.sldasm', '.slddrw']):
            return found_files
        
        try:
            for root, dirs, files in os.walk(self.cad_root):
                for file in files:
                    if file.lower() == filename.lower():
                        found_files.append(os.path.join(root, file))
        except Exception as e:
            print(f"Error searching for file {filename}: {e}")
        
        return found_files
    
    def create_lock(self, file_path):
        """Create a lock file"""
        lock_path = self.get_lock_path(file_path)
        
        if os.path.exists(lock_path):
            # Check if it's our lock
            try:
                with open(lock_path, 'r') as f:
                    lock_data = json.load(f)
                if lock_data.get('user') == self.user:
                    return True  # Already our lock
                else:
                    return False  # Someone else's lock
            except:
                pass
        
        lock_data = {
            'user': self.user,
            'computer': self.computer,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'file': os.path.basename(file_path),
            'original_path': file_path,
            'lock_file': lock_path,
            'auto_created': True
        }
        
        try:
            with open(lock_path, 'w') as f:
                json.dump(lock_data, f, indent=2)
            print(f"🔒 Auto-locked: {os.path.basename(file_path)}")
            return True
        except Exception as e:
            print(f"Failed to create lock for {file_path}: {e}")
            return False
    
    def remove_lock(self, file_path):
        """Remove a lock file"""
        lock_path = self.get_lock_path(file_path)
        
        if os.path.exists(lock_path):
            try:
                # Check if it's our lock before removing
                with open(lock_path, 'r') as f:
                    lock_data = json.load(f)
                
                if lock_data.get('user') == self.user or lock_data.get('computer') == self.computer:
                    os.remove(lock_path)
                    print(f"🔓 Auto-unlocked: {os.path.basename(file_path)}")
                    return True
                else:
                    print(f"Cannot remove lock - owned by {lock_data.get('user')}")
                    return False
            except Exception as e:
                print(f"Error removing lock for {file_path}: {e}")
                return False
        return True
    
    def get_lock_path(self, file_path):
        """Generate lock file path in centralized directory"""
        try:
            rel_path = os.path.relpath(file_path, self.cad_root)
        except ValueError:
            rel_path = file_path.replace(':', '_').replace('\\', '_').replace('/', '_')
        
        safe_path = rel_path.replace('\\', '_').replace('/', '_').replace(':', '_')
        safe_path = safe_path.replace('*', '_').replace('?', '_').replace('"', '_')
        safe_path = safe_path.replace('<', '_').replace('>', '_').replace('|', '_')
        
        lock_filename = f"{safe_path}.lock"
        return os.path.join(self.lock_dir, lock_filename)
    
    def get_my_current_locks(self):
        """Get all locks currently owned by this user"""
        my_locks = set()
        
        if not os.path.exists(self.lock_dir):
            return my_locks
        
        try:
            for lock_file in os.listdir(self.lock_dir):
                if lock_file.endswith('.lock'):
                    lock_path = os.path.join(self.lock_dir, lock_file)
                    try:
                        with open(lock_path, 'r') as f:
                            lock_data = json.load(f)
                        
                        if (lock_data.get('user') == self.user and 
                            lock_data.get('auto_created', False)):
                            original_path = lock_data.get('original_path')
                            if original_path:
                                my_locks.add(original_path)
                    except (json.JSONDecodeError, KeyError):
                        continue
        except Exception as e:
            print(f"Error reading locks: {e}")
        
        return my_locks
    
    def monitor_files(self):
        """Main monitoring loop"""
        print("🔍 Starting automatic lock monitoring...")
        print(f"👤 User: {self.user}")
        print(f"💻 Computer: {self.computer}")
        print(f"📁 Monitoring: {self.cad_root}")
        print("=" * 50)
        
        while self.running:
            try:
                # Get currently open files
                open_files = self.get_open_solidworks_files()
                
                # Get our current locks
                current_locks = self.get_my_current_locks()
                
                # Create locks for newly opened files
                for file_path in open_files:
                    if file_path not in current_locks:
                        self.create_lock(file_path)
                
                # Remove locks for files that are no longer open
                for locked_file in current_locks:
                    if locked_file not in open_files:
                        # Double-check the file isn't open before removing lock
                        if not os.path.exists(locked_file) or locked_file not in open_files:
                            self.remove_lock(locked_file)
                
                # Update status
                if open_files:
                    print(f"📂 Currently open: {len(open_files)} files")
                    for file_path in open_files:
                        print(f"   • {os.path.basename(file_path)}")
                else:
                    print("💤 No CAD files currently open")
                
                time.sleep(10)  # Check every 10 seconds
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(5)
        
        print("🛑 Monitoring stopped")
    
    def start_monitoring(self):
        """Start the monitoring in a separate thread"""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self.monitor_files, daemon=True)
            self.monitor_thread.start()
            return True
        return False
    
    def stop_monitoring(self):
        """Stop the monitoring"""
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        # Clean up all our auto-created locks
        my_locks = self.get_my_current_locks()
        for locked_file in my_locks:
            self.remove_lock(locked_file)

def main():
    """Main function to run the monitor"""
    monitor = AutoLockMonitor()
    
    print("🚀 CAD Auto-Lock Monitor")
    print("This will automatically create and remove locks based on open SolidWorks files")
    print("Press Ctrl+C to stop monitoring")
    print()
    
    try:
        monitor.start_monitoring()
        
        # Keep the main thread alive
        while monitor.running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n👋 Stopping monitor...")
        monitor.stop_monitoring()
        print("✅ All locks cleaned up")

if __name__ == "__main__":
    main()