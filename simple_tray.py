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
        
        # Collision animation state
        self.collision_active = False
        self.animation_thread = None
        
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
            image = Image.new('RGBA', (32, 32), (255, 0, 0, 255))  # Bright red for collision
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
            # Different colored circle based on warning state
            circle_color = (255, 255, 0, 255) if warning else (255, 0, 0, 255)  # Yellow for warning, red for normal
            draw.ellipse([20, 2, 30, 12], fill=circle_color)
            # Black number for better contrast
            count_str = str(min(lock_count, 9))  # Single digit only
            draw.text((23, 4), count_str, fill=(0, 0, 0, 255))
        
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
        """Show warning dialog for editing collision - more reliable popup"""
        try:
            filename = os.path.basename(file_path)
            locked_by = lock_info.get('user', 'Unknown')
            locked_since = lock_info.get('timestamp', 'Unknown')
            
            # Start collision animation
            self.start_collision_animation()
            
            # Force the popup to appear on top
            root = tk.Tk()
            root.withdraw()
            root.lift()
            root.attributes('-topmost', True)
            root.attributes('-alpha', 0.0)  # Make invisible
            root.focus_force()
            
            message = f"⚠️ COLLISION WARNING ⚠️\n\n"
            message += f"You are editing: {filename}\n"
            message += f"But it's locked by: {locked_by}\n"
            message += f"Since: {locked_since}\n\n"
            message += f"You may not be able to save your changes!\n"
            message += f"Consider coordinating with {locked_by}."
            
            # Use a more aggressive popup method
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, 
                message, 
                "CAD Lock System - Collision Warning", 
                0x30  # Warning icon + OK button
            )
            
            root.destroy()
            
            self.log_message(f"COLLISION WARNING SHOWN: {filename} locked by {locked_by}")
            
        except Exception as e:
            self.log_message(f"Error showing collision warning: {e}")
            # Fallback to console alert
            print(f"\n*** COLLISION WARNING ***")
            print(f"File: {os.path.basename(file_path)}")
            print(f"Locked by: {lock_info.get('user')}")
            print("*************************\n")
    
    def start_collision_animation(self):
        """Start animated icon for collision"""
        if not self.collision_active:
            self.collision_active = True
            if self.animation_thread is None or not self.animation_thread.is_alive():
                self.animation_thread = threading.Thread(target=self.animate_collision_icon, daemon=True)
                self.animation_thread.start()
    
    def stop_collision_animation(self):
        """Stop collision animation"""
        self.collision_active = False
    
    def animate_collision_icon(self):
        """Animate the tray icon during collision"""
        flash_count = 0
        while self.collision_active and flash_count < 6:  # Flash 3 times (6 state changes)
            try:
                if hasattr(self, 'tray_icon') and self.tray_icon:
                    lock_count = self.get_my_lock_count()
                    
                    # Alternate between bright red and dark red
                    if flash_count % 2 == 0:
                        # Bright red flash
                        image = Image.new('RGBA', (32, 32), (255, 0, 0, 255))
                    else:
                        # Dark red
                        image = Image.new('RGBA', (32, 32), (150, 0, 0, 255))
                    
                    draw = ImageDraw.Draw(image)
                    # White border
                    draw.rectangle([0, 0, 31, 31], outline=(255, 255, 255, 255), width=2)
                    # Draw "L" in center
                    draw.rectangle([8, 8, 12, 24], fill=(255, 255, 255, 255))
                    draw.rectangle([8, 20, 20, 24], fill=(255, 255, 255, 255))
                    
                    # Add exclamation mark for collision
                    draw.rectangle([14, 8, 18, 20], fill=(255, 255, 255, 255))  # Exclamation line
                    draw.rectangle([14, 22, 18, 24], fill=(255, 255, 255, 255))  # Exclamation dot
                    
                    self.tray_icon.icon = image
                    self.tray_icon.title = "🚨 COLLISION DETECTED! 🚨"
                
                time.sleep(0.5)  # Flash every 0.5 seconds
                flash_count += 1
                
            except Exception as e:
                self.log_message(f"Error in collision animation: {e}")
                break
        
        # After animation, set to solid red if collision still active
        if self.collision_active:
            self.update_icon(warning=True)
    
    def try_close_file_in_solidworks(self, file_path):
        """Try to close the file in SolidWorks using COM automation"""
        try:
            import win32com.client
            
            # Try to connect to SolidWorks
            sw = win32com.client.Dispatch("SldWorks.Application")
            
            # Get the active document
            doc = sw.GetFirstDocument()
            while doc:
                doc_path = doc.GetPathName()
                if doc_path.lower() == file_path.lower():
                    # Close this document
                    sw.CloseDoc(doc.GetTitle())
                    self.log_message(f"Closed {os.path.basename(file_path)} in SolidWorks")
                    break
                doc = doc.GetNext()
                
        except Exception as e:
            self.log_message(f"Could not close file in SolidWorks: {e}")
            # This is expected if SolidWorks COM isn't available
    
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
    
    def protect_all_locked_files(self):
        """Proactively protect all files that are locked by others"""
        try:
            if not os.path.exists(self.lock_dir):
                return
                
            for lock_file in os.listdir(self.lock_dir):
                if lock_file.endswith('.lock'):
                    lock_path = os.path.join(self.lock_dir, lock_file)
                    try:
                        with open(lock_path, 'r') as f:
                            lock_data = json.load(f)
                        
                        locked_by = lock_data.get('user')
                        original_path = lock_data.get('original_path')
                        
                        # If file is locked by someone else and exists
                        if (locked_by and locked_by != self.user and 
                            original_path and os.path.exists(original_path)):
                            
                            # More aggressive: Move file to hidden location
                            self.hide_locked_file(original_path, lock_data)
                                    
                    except Exception as e:
                        self.log_message(f"Error processing lock file {lock_file}: {e}")
                        
        except Exception as e:
            self.log_message(f"Error in protect_all_locked_files: {e}")
    
    def hide_locked_file(self, file_path, lock_data):
        """Move locked file to hidden location to prevent access"""
        try:
            if not hasattr(self, 'hidden_files'):
                self.hidden_files = {}
            
            # If already hidden, skip
            if file_path in self.hidden_files:
                return
                
            # Create hidden directory
            hidden_dir = os.path.join(os.path.dirname(file_path), ".cad_lock_hidden")
            os.makedirs(hidden_dir, exist_ok=True)
            
            # Move file to hidden location
            filename = os.path.basename(file_path)
            hidden_path = os.path.join(hidden_dir, filename)
            
            # If hidden file already exists, use timestamp suffix
            if os.path.exists(hidden_path):
                name, ext = os.path.splitext(filename)
                timestamp = datetime.now().strftime("%H%M%S")
                hidden_path = os.path.join(hidden_dir, f"{name}_{timestamp}{ext}")
            
            # Move the file
            import shutil
            shutil.move(file_path, hidden_path)
            
            # Track the move
            self.hidden_files[file_path] = {
                'hidden_path': hidden_path,
                'locked_by': lock_data.get('user'),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self.log_message(f"HIDDEN: {filename} locked by {lock_data.get('user')} - moved to hidden location")
            
        except Exception as e:
            self.log_message(f"Error hiding file {file_path}: {e}")
    
    def restore_hidden_files(self):
        """Restore any hidden files when locks are released"""
        try:
            if not hasattr(self, 'hidden_files'):
                return
                
            files_to_restore = []
            
            for original_path, hide_info in self.hidden_files.items():
                # Check if file is still locked by someone else
                lock_info = self.get_lock_info(original_path)
                
                if not lock_info or lock_info.get('user') == self.user:
                    # Lock released or is ours now - restore file
                    files_to_restore.append(original_path)
            
            # Restore files
            for original_path in files_to_restore:
                hide_info = self.hidden_files[original_path]
                hidden_path = hide_info['hidden_path']
                
                try:
                    if os.path.exists(hidden_path):
                        import shutil
                        shutil.move(hidden_path, original_path)
                        self.log_message(f"RESTORED: {os.path.basename(original_path)} - lock released")
                    
                    del self.hidden_files[original_path]
                    
                except Exception as e:
                    self.log_message(f"Error restoring {original_path}: {e}")
                    
        except Exception as e:
            self.log_message(f"Error restoring hidden files: {e}")
    
    def restore_file_permissions(self, file_path):
        """Restore normal file permissions"""
        try:
            import stat
            os.chmod(file_path, stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH)
            self.log_message(f"Restored permissions for {os.path.basename(file_path)}")
        except Exception as e:
            self.log_message(f"Error restoring permissions for {file_path}: {e}")
    
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
                    
                    # Show warning every time (remove the "warn once" limitation)
                    self.show_collision_warning(file_path, lock_info)
                    collisions_found = True
                    
                    self.log_message(f"COLLISION: {filename} locked by {locked_by}")
        
        # Stop animation if no more collisions
        if not collisions_found and self.collision_active:
            self.stop_collision_animation()
        
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
                
                if warning:
                    title = f"🚨 COLLISION! {lock_count} files locked 🚨"
                else:
                    title = f"CAD Locks: {lock_count} files"
                    
                self.tray_icon.title = title
        except Exception as e:
            print(f"Error updating icon: {e}")
    
    def start_monitoring(self, icon=None, item=None):
        """Start monitoring"""
        if not self.monitor_running:
            self.monitor_running = True
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()
            self.log_message("Monitoring started with collision detection")
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