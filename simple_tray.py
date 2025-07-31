import os
import json
import sys
import time
import threading
from datetime import datetime
import psutil
import pystray
from PIL import Image, ImageDraw
import tkinter as tk
from tkinter import messagebox
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import tkinter as tk
from tkinter import messagebox

# Simple version with collision detection
class SimpleCADTray:
    def __init__(self):
        self.user = os.getenv('USER_OVERRIDE') or os.getenv('USERNAME')
        self.computer = os.getenv('COMPUTER_OVERRIDE') or os.getenv('COMPUTERNAME')
        
        # Get paths from environment variables (set by config.bat) (set by config.bat)
        self.lock_dir = os.getenv('LOCK_DIR', r"G:\Shared drives\Cosmic\Engineering\50 - CAD Data\Locks")
        self.cad_root = os.getenv('CAD_ROOT_DIR', r"G:\Shared drives\Cosmic\Engineering\50 - CAD Data")
        
        # Get settings
        self.monitor_interval = int(os.getenv('MONITOR_INTERVAL', '10'))
        
        self.monitor_running = False
        self.monitor_thread = None
        self.log_entries = []
        
        # Track files we've already warned about to avoid spam
        self.warned_files = set()
        
        # File system watcher for save interception
        self.file_observer = None
        self.save_handler = None
        
        # Track files we've already warned about to avoid spam
        self.warned_files = set()
        
        # Ensure directories exist
        os.makedirs(self.lock_dir, exist_ok=True)
        
        print(f"SimpleCADTray initialized for user: {self.user}")
        self._validate_paths()
    
    def _validate_paths(self):
        """Validate that required paths exist"""
        if not os.path.exists(self.cad_root):
            print(f"Warning: CAD root directory not found: {self.cad_root}")
        if not os.path.exists(self.lock_dir):
            print(f"Creating lock directory: {self.lock_dir}")
    
    def create_simple_icon(self, lock_count=0, warning=False):
        """Create a very simple icon"""
        # Create a simple 32x32 icon
        if warning:
            image = Image.new('RGBA', (32, 32), (255, 69, 0, 255))  # Orange/red for warning
        else:
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
    
    def get_lock_info(self, file_path):
        """Get lock information for a specific file"""
        try:
            # Generate lock path like main.py does
            rel_path = os.path.relpath(file_path, self.cad_root)
            safe_path = rel_path.replace('\\', '_').replace('/', '_').replace(':', '_')
            safe_path = safe_path.replace('*', '_').replace('?', '_').replace('"', '_')
            safe_path = safe_path.replace('<', '_').replace('>', '_').replace('|', '_')
            
            lock_filename = f"{safe_path}.lock"
            lock_path = os.path.join(self.lock_dir, lock_filename)
            
            if os.path.exists(lock_path):
                with open(lock_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.log_message(f"Error checking lock for {file_path}: {e}")
        return None
    
    def show_collision_warning(self, file_path, lock_info):
        """Show warning dialog for editing collision"""
        try:
            # Create warning dialog
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            root.attributes('-topmost', True)  # Make sure it appears on top
            
            filename = os.path.basename(file_path)
            locked_by = lock_info.get('user', 'Unknown')
            locked_since = lock_info.get('timestamp', 'Unknown')
            
            message = f"⚠️ EDITING COLLISION DETECTED ⚠️\n\n"
            message += f"File: {filename}\n"
            message += f"Locked by: {locked_by}\n"
            message += f"Since: {locked_since}\n\n"
            message += f"You are editing a file that is locked by another user!\n"
            message += f"You will NOT be able to save your changes.\n\n"
            message += f"Consider closing the file and coordinating with {locked_by}."
            
            # Show warning message
            messagebox.showwarning(
                "CAD Lock System - Editing Collision", 
                message
            )
            
            root.destroy()
            
            self.log_message(f"COLLISION WARNING: {filename} locked by {locked_by}")
            
        except Exception as e:
            self.log_message(f"Error showing collision warning: {e}")
    
    def check_for_collisions(self, open_files):
        """Check if any of my open files are locked by others"""
        collisions_found = False
        
        for file_path in open_files:
            lock_info = self.get_lock_info(file_path)
            
            if lock_info:
                locked_by = lock_info.get('user')
                
                # If file is locked by someone else
                if locked_by and locked_by != self.user:
                    filename = os.path.basename(file_path)
                    
                    # Only warn once per file per session
                    if file_path not in self.warned_files:
                        self.show_collision_warning(file_path, lock_info)
                        self.warned_files.add(file_path)
                        collisions_found = True
                    
                    self.log_message(f"COLLISION: {filename} locked by {locked_by}")
        
        return collisions_found
    
    def check_save_attempt(self, file_path):
        """Check if user is trying to save a locked file"""
        try:
            lock_info = self.get_lock_info(file_path)
            
            if lock_info:
                locked_by = lock_info.get('user')
                
                # If file is locked by someone else
                if locked_by and locked_by != self.user:
                    self.show_save_blocked_warning(file_path, lock_info)
                    # Immediately make file read-only to prevent further saves
                    self.make_file_readonly_permanently(file_path, lock_info)
                    return True
                    
        except Exception as e:
            self.log_message(f"Error checking save attempt: {e}")
        return False
    
    def make_file_readonly_permanently(self, file_path, lock_info):
        """Make file read-only and keep a file handle open to prevent writing"""
        try:
            import stat
            
            # First, try to make file read-only
            os.chmod(file_path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
            
            # More aggressive: Try to keep file handle open for reading to prevent writing
            try:
                file_handle = open(file_path, 'rb')
                # Store handle so it stays open
                if not hasattr(self, 'blocked_files'):
                    self.blocked_files = {}
                self.blocked_files[file_path] = file_handle
                
                self.log_message(f"Blocked file handle for {os.path.basename(file_path)}")
            except Exception as e:
                self.log_message(f"Could not open file handle for {file_path}: {e}")
            
            # Store in lock data
            lock_path = self.get_lock_path_from_file(file_path)
            if os.path.exists(lock_path):
                with open(lock_path, 'r') as f:
                    lock_data = json.load(f)
                
                lock_data['made_readonly_by_collision'] = True
                lock_data['blocked_timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                with open(lock_path, 'w') as f:
                    json.dump(lock_data, f, indent=2)
            
            self.log_message(f"Made {os.path.basename(file_path)} read-only due to lock conflict")
            
        except Exception as e:
            self.log_message(f"Error setting readonly: {e}")
    
    def release_blocked_files(self):
        """Release any blocked file handles"""
        try:
            if hasattr(self, 'blocked_files'):
                for file_path, handle in list(self.blocked_files.items()):
                    try:
                        handle.close()
                        del self.blocked_files[file_path]
                        
                        # Restore normal permissions
                        import stat
                        os.chmod(file_path, stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IWGRP)
                        
                        self.log_message(f"Released block on {os.path.basename(file_path)}")
                    except:
                        pass
        except Exception as e:
            self.log_message(f"Error releasing blocked files: {e}")
    
    def check_for_collisions(self, open_files):
        """Check if any of my open files are locked by others"""
        collisions_found = False
        current_collisions = set()
        
        for file_path in open_files:
            lock_info = self.get_lock_info(file_path)
            
            if lock_info:
                locked_by = lock_info.get('user')
                
                # If file is locked by someone else
                if locked_by and locked_by != self.user:
                    filename = os.path.basename(file_path)
                    current_collisions.add(file_path)
                    
                    # Only warn once per file per session
                    if file_path not in self.warned_files:
                        self.show_collision_warning(file_path, lock_info)
                        self.warned_files.add(file_path)
                        collisions_found = True
                        
                        # Immediately try to block the file
                        self.make_file_readonly_permanently(file_path, lock_info)
                        
                        # Show additional warning about saving
                        self.show_save_prevention_warning(file_path, lock_info)
                    
                    self.log_message(f"COLLISION: {filename} locked by {locked_by}")
        
        # Release blocks on files no longer in collision
        if hasattr(self, 'blocked_files'):
            for blocked_path in list(self.blocked_files.keys()):
                if blocked_path not in current_collisions:
                    try:
                        handle = self.blocked_files[blocked_path]
                        handle.close()
                        del self.blocked_files[blocked_path]
                        
                        # Restore permissions
                        import stat
                        os.chmod(blocked_path, stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IWGRP)
                        
                        self.log_message(f"Released block on {os.path.basename(blocked_path)} - no longer in collision")
                    except:
                        pass
        
        return collisions_found
    
    def show_save_prevention_warning(self, file_path, lock_info):
        """Show additional warning about save prevention"""
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            filename = os.path.basename(file_path)
            locked_by = lock_info.get('user', 'Unknown')
            
            message = f"🚫 SAVE PROTECTION ACTIVATED 🚫\n\n"
            message += f"File: {filename}\n"
            message += f"Locked by: {locked_by}\n\n"
            message += f"This file has been made read-only to prevent\n"
            message += f"data conflicts. SolidWorks should show this\n"
            message += f"file as read-only in the title bar.\n\n"
            message += f"Any save attempts will be blocked until\n"
            message += f"{locked_by} releases the lock."
            
            messagebox.showinfo(
                "CAD Lock System - Save Protection", 
                message
            )
            
            root.destroy()
            
        except Exception as e:
            self.log_message(f"Error showing save prevention warning: {e}")
    
    def get_lock_path_from_file(self, file_path):
        """Get lock file path for a given file"""
        try:
            rel_path = os.path.relpath(file_path, self.cad_root)
            safe_path = rel_path.replace('\\', '_').replace('/', '_').replace(':', '_')
            safe_path = safe_path.replace('*', '_').replace('?', '_').replace('"', '_')
            safe_path = safe_path.replace('<', '_').replace('>', '_').replace('|', '_')
            
            lock_filename = f"{safe_path}.lock"
            return os.path.join(self.lock_dir, lock_filename)
        except:
            return None
    
    def show_save_blocked_warning(self, file_path, lock_info):
        """Show warning that save is blocked"""
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            filename = os.path.basename(file_path)
            locked_by = lock_info.get('user', 'Unknown')
            locked_since = lock_info.get('timestamp', 'Unknown')
            
            message = f"🚫 SAVE BLOCKED 🚫\n\n"
            message += f"Cannot save file: {filename}\n\n"
            message += f"File is locked by: {locked_by}\n"
            message += f"Since: {locked_since}\n\n"
            message += f"Your changes cannot be saved while the file is locked.\n"
            message += f"Contact {locked_by} to coordinate access."
            
            messagebox.showerror(
                "CAD Lock System - Save Blocked", 
                message
            )
            
            root.destroy()
            
            self.log_message(f"SAVE BLOCKED: {filename} locked by {locked_by}")
            
        except Exception as e:
            self.log_message(f"Error showing save blocked warning: {e}")
    
    def make_file_readonly_temporarily(self, file_path):
        """Temporarily make file read-only to prevent save"""
        try:
            import stat
            # Make file read-only for 5 seconds
            current_mode = os.stat(file_path).st_mode
            os.chmod(file_path, stat.S_IREAD)
            
            # Restore permissions after 5 seconds
            def restore_permissions():
                try:
                    time.sleep(5)
                    os.chmod(file_path, current_mode)
                    self.log_message(f"Restored permissions for {os.path.basename(file_path)}")
                except:
                    pass
            
            threading.Thread(target=restore_permissions, daemon=True).start()
            
        except Exception as e:
            self.log_message(f"Error setting readonly: {e}")
    
    def make_locked_files_readonly(self):
        """Make all files locked by others read-only"""
        try:
            open_files = self.find_open_files()
            
            for file_path in open_files:
                lock_info = self.get_lock_info(file_path)
                
                if lock_info:
                    locked_by = lock_info.get('user')
                    
                    # If file is locked by someone else, make it read-only
                    if locked_by and locked_by != self.user:
                        self.make_file_readonly_permanently(file_path, lock_info)
                        
        except Exception as e:
            self.log_message(f"Error making locked files readonly: {e}")
    
    def start_file_watcher(self):
        """Start file system watcher for save interception"""
        try:
            if self.file_observer is None:
                self.save_handler = SaveInterceptHandler(self)
                self.file_observer = Observer()
                self.file_observer.schedule(self.save_handler, self.cad_root, recursive=True)
                self.file_observer.start()
                self.log_message("File system watcher started for save interception")
        except Exception as e:
            self.log_message(f"Error starting file watcher: {e}")
    
    def stop_file_watcher(self):
        """Stop file system watcher"""
        try:
            if self.file_observer:
                self.file_observer.stop()
                self.file_observer.join()
                self.file_observer = None
                self.save_handler = None
                self.log_message("File system watcher stopped")
        except Exception as e:
            self.log_message(f"Error stopping file watcher: {e}")
    
    def get_lock_info(self, file_path):
        """Get lock information for a specific file"""
        try:
            # Generate lock path like main.py does
            rel_path = os.path.relpath(file_path, self.cad_root)
            safe_path = rel_path.replace('\\', '_').replace('/', '_').replace(':', '_')
            safe_path = safe_path.replace('*', '_').replace('?', '_').replace('"', '_')
            safe_path = safe_path.replace('<', '_').replace('>', '_').replace('|', '_')
            
            lock_filename = f"{safe_path}.lock"
            lock_path = os.path.join(self.lock_dir, lock_filename)
            
            if os.path.exists(lock_path):
                with open(lock_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.log_message(f"Error checking lock for {file_path}: {e}")
        return None
    
    def show_collision_warning(self, file_path, lock_info):
        """Show warning dialog for editing collision"""
        try:
            # Create warning dialog
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            root.attributes('-topmost', True)  # Make sure it appears on top
            
            filename = os.path.basename(file_path)
            locked_by = lock_info.get('user', 'Unknown')
            locked_since = lock_info.get('timestamp', 'Unknown')
            
            message = f"⚠️ EDITING COLLISION DETECTED ⚠️\n\n"
            message += f"File: {filename}\n"
            message += f"Locked by: {locked_by}\n"
            message += f"Since: {locked_since}\n\n"
            message += f"You are editing a file that is locked by another user!\n"
            message += f"You will NOT be able to save your changes.\n\n"
            message += f"Consider closing the file and coordinating with {locked_by}."
            
            # Show warning message
            messagebox.showwarning(
                "CAD Lock System - Editing Collision", 
                message
            )
            
            root.destroy()
            
            self.log_message(f"COLLISION WARNING: {filename} locked by {locked_by}")
            
        except Exception as e:
            self.log_message(f"Error showing collision warning: {e}")
    
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
                self.log_message(f"Found {len(temp_files_found)} temp files")
            else:
                self.log_message("No temp files found in CAD directory")
                            
        except Exception as e:
            self.log_message(f"Error scanning for open files: {e}")
            
        return open_files
    
    def check_for_collisions(self, open_files):
        """Check if any of my open files are locked by others"""
        collisions_found = False
        
        for file_path in open_files:
            lock_info = self.get_lock_info(file_path)
            
            if lock_info:
                locked_by = lock_info.get('user')
                
                # If file is locked by someone else
                if locked_by and locked_by != self.user:
                    filename = os.path.basename(file_path)
                    
                    # Only warn once per file per session
                    if file_path not in self.warned_files:
                        self.show_collision_warning(file_path, lock_info)
                        self.warned_files.add(file_path)
                        collisions_found = True
                    
                    self.log_message(f"COLLISION: {filename} locked by {locked_by}")
        
        return collisions_found
    
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
        """Main monitoring loop with collision detection"""
        self.log_message("Monitor started with collision detection")
        
        while self.monitor_running:
            try:
                sw_running = self.is_solidworks_running()
                self.log_message(f"SolidWorks running: {sw_running}")
                
                collision_detected = False
                
                if sw_running:
                    # Get currently open files
                    open_files = self.find_open_files()
                    self.log_message(f"Found {len(open_files)} open files")
                    
                    # Check for collisions FIRST
                    collision_detected = self.check_for_collisions(open_files)
                    
                    # Make any files locked by others read-only
                    self.make_locked_files_readonly()
                    
                    # Create locks for open files (only if not locked by others)
                    for file_path in open_files:
                        lock_info = self.get_lock_info(file_path)
                        
                        # Only create lock if file isn't locked by someone else
                        if not lock_info or lock_info.get('user') == self.user:
                            self.create_lock(file_path)
                    
                    # Remove locks for files that are no longer open
                    try:
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
                
                # Update icon with current counts (show warning if collision detected)
                self.update_icon(warning=collision_detected)
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                self.log_message(f"Monitor error: {e}")
                time.sleep(5)
        
        self.log_message("Monitor stopped")
    
    def update_icon(self, warning=False):
        """Update tray icon"""
        try:
            if hasattr(self, 'tray_icon') and self.tray_icon:
                lock_count = self.get_my_lock_count()
                self.tray_icon.icon = self.create_simple_icon(lock_count, warning)
                title = f"CAD Locks: {lock_count} files"
                if warning:
                    title += " ⚠️ COLLISION!"
                self.tray_icon.title = title
        except Exception as e:
            print(f"Error updating icon: {e}")
    
    def start_monitoring(self, icon=None, item=None):
        """Start monitoring"""
        if not self.monitor_running:
            self.monitor_running = True
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()
            self.start_file_watcher()  # Start save interception
            self.log_message("Monitoring started with save interception")
            self.update_icon()
    
    def stop_monitoring(self, icon=None, item=None):
        """Stop monitoring"""
        if self.monitor_running:
            self.monitor_running = False
            self.stop_file_watcher()  # Stop save interception
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
        self.release_blocked_files()  # Release any file blocks
        self.stop_monitoring()
        self.stop_file_watcher()
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