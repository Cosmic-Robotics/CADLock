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

# Simple version with collision detection
class SimpleCADTray:
    def __init__(self):
        self.user = os.getenv('USER_OVERRIDE') or os.getenv('USERNAME')
        self.computer = os.getenv('COMPUTER_OVERRIDE') or os.getenv('COMPUTERNAME')
        
        # Get paths from environment variables (set by config.bat)
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
    
    def check_for_collisions(self, open_files):
        """Check for ALL collision scenarios"""
        collisions_found = False
        
        # Scenario 1: I'm editing a file locked by someone else
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
                    
                    self.log_message(f"COLLISION TYPE 1: {filename} locked by {locked_by}")
        
        # Scenario 2: Check if multiple people have locks on the same file
        # This is the crucial line that checks for multiple locks!
        multiple_locks_found = self.check_for_multiple_locks()
        collisions_found = collisions_found or multiple_locks_found
        
        # Stop animation if no more collisions
        if not collisions_found and self.collision_active:
            self.stop_collision_animation()
        
        return collisions_found
        
    def check_for_multiple_locks(self):
        """Check if multiple users have locks on the same file"""
        conflicts_found = False
        
        try:
            if not os.path.exists(self.lock_dir):
                self.log_message("Lock directory doesn't exist - no conflicts possible")
                return False
            
            # Group locks by file path AND by normalized file path
            file_locks = {}
            
            lock_files = [f for f in os.listdir(self.lock_dir) if f.endswith('.lock')]
            self.log_message(f"Checking {len(lock_files)} lock files for conflicts")
            
            for lock_file in lock_files:
                lock_path = os.path.join(self.lock_dir, lock_file)
                try:
                    with open(lock_path, 'r') as f:
                        lock_data = json.load(f)
                    
                    original_path = lock_data.get('original_path', '')
                    user = lock_data.get('user', '')
                    
                    if original_path and user:
                        # Normalize the path to catch different representations of same file
                        normalized_path = os.path.normpath(original_path.lower())
                        
                        # Use both original and normalized paths as keys
                        for key in [original_path, normalized_path]:
                            if key not in file_locks:
                                file_locks[key] = []
                            file_locks[key].append({
                                'user': user,
                                'lock_file': lock_file,
                                'original_path': original_path,
                                'data': lock_data
                            })
                        
                        self.log_message(f"Found lock: {os.path.basename(original_path)} by {user}")
                            
                except Exception as e:
                    self.log_message(f"Error reading lock file {lock_file}: {e}")
                    continue
            
            # Check for files with multiple locks
            checked_files = set()
            for file_path, locks in file_locks.items():
                if file_path in checked_files:
                    continue
                    
                if len(locks) > 1:
                    # Remove duplicates (same user might appear multiple times due to normalization)
                    unique_users = {}
                    for lock in locks:
                        user = lock['user']
                        if user not in unique_users:
                            unique_users[user] = lock
                    
                    if len(unique_users) > 1:
                        # Multiple people have this file locked!
                        users = list(unique_users.keys())
                        filename = os.path.basename(file_path)
                        
                        self.log_message(f"CONFLICT DETECTED: {filename} locked by multiple users: {', '.join(users)}")
                        
                        # ALWAYS start animation when ANY collision is detected
                        self.start_collision_animation()
                        conflicts_found = True
                        
                        # Mark this file as checked to avoid duplicate processing
                        checked_files.add(file_path)
                        for lock in locks:
                            checked_files.add(lock['original_path'])
                            checked_files.add(os.path.normpath(lock['original_path'].lower()))
                        
                        # Show popup warning only if we're one of the users involved
                        if self.user in users:
                            other_users = [u for u in users if u != self.user]
                            self.show_multiple_lock_warning(file_path, other_users)
                        else:
                            # We're not involved, but still show a notification about the conflict
                            self.log_message(f"CONFLICT (not involving me): {filename} locked by {', '.join(users)}")
                            
                            # Optionally, show a different warning for conflicts not involving us
                            self.show_conflict_notification(file_path, users)
                        
        except Exception as e:
            self.log_message(f"Error in check_for_multiple_locks: {e}")
            
        if not conflicts_found:
            self.log_message("No multiple lock conflicts found")
            
        return conflicts_found
    
    def show_multiple_lock_warning(self, file_path, other_users):
        """Show warning when multiple users have the same file locked"""
        try:
            filename = os.path.basename(file_path)
            
            # Start collision animation
            self.start_collision_animation()
            
            # Force the popup to appear on top
            root = tk.Tk()
            root.withdraw()
            root.lift()
            root.attributes('-topmost', True)
            root.attributes('-alpha', 0.0)  # Make invisible
            root.focus_force()
            
            message = f"🚨 MULTIPLE LOCKS DETECTED 🚨\n\n"
            message += f"File: {filename}\n"
            message += f"Also locked by: {', '.join(other_users)}\n\n"
            message += f"Multiple people are editing the same file!\n"
            message += f"This will cause conflicts when saving.\n\n"
            message += f"Coordinate with {', '.join(other_users)} immediately!"
            
            # Use Windows MessageBox for reliability
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, 
                message, 
                "CAD Lock System - Multiple Locks!", 
                0x30  # Warning icon + OK button
            )
            
            root.destroy()
            
            self.log_message(f"MULTIPLE LOCK WARNING SHOWN: {filename} also locked by {', '.join(other_users)}")
            
        except Exception as e:
            self.log_message(f"Error showing multiple lock warning: {e}")
            # Fallback to console alert
            print(f"\n*** MULTIPLE LOCKS WARNING ***")
            print(f"File: {os.path.basename(file_path)}")
            print(f"Also locked by: {', '.join(other_users)}")
            print("******************************\n")

    def show_conflict_notification(self, file_path, users):
        """Show notification about conflicts between other users"""
        try:
            filename = os.path.basename(file_path)
            
            # Only show this notification once per conflict
            conflict_key = f"{filename}:{','.join(sorted(users))}"
            if not hasattr(self, 'notified_conflicts'):
                self.notified_conflicts = set()
            
            if conflict_key not in self.notified_conflicts:
                self.notified_conflicts.add(conflict_key)
                
                # Update tray icon tooltip to show conflict
                if hasattr(self, 'tray_icon') and self.tray_icon:
                    self.tray_icon.title = f"⚠️ CONFLICT: {filename} locked by {len(users)} users!"
                
                # Log the conflict prominently
                self.log_message(f"*** SYSTEM CONFLICT ALERT ***")
                self.log_message(f"File: {filename}")
                self.log_message(f"Locked by: {', '.join(users)}")
                self.log_message(f"*****************************")
                
        except Exception as e:
            self.log_message(f"Error showing conflict notification: {e}")

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
    
    def create_lock(self, file_path):
        """Create lock file"""
        try:
            # Simple lock path generation
            rel_path = os.path.relpath(file_path, self.cad_root)
            safe_path = rel_path.replace('\\', '_').replace('/', '_').replace(':', '_')
            safe_path = safe_path.replace('*', '_').replace('?', '_').replace('"', '_')
            safe_path = safe_path.replace('<', '_').replace('>', '_').replace('|', '_')
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
            safe_path = safe_path.replace('<', '_').replace('>', '_').replace('|', '_')
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
                    
                    # Check for collisions FIRST (this includes multiple lock detection)
                    collision_detected = self.check_for_collisions(open_files)
                    
                    # Even if no collision from open files, check for ANY multiple locks in the system
                    if not collision_detected:
                        collision_detected = self.check_for_multiple_locks()
                    
                    # Create locks for ALL open files - ensure every open file has a lock from me
                    for file_path in open_files:
                        # Check if I already have a lock for this file
                        existing_lock = self.get_lock_info(file_path)
                        
                        if not existing_lock or existing_lock.get('user') != self.user:
                            # I don't have a lock for this file - create one
                            lock_data = {
                                'user': self.user,
                                'computer': self.computer,
                                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'file': os.path.basename(file_path),
                                'original_path': file_path,
                                'auto_created': True,
                                'detection_method': 'temp_file_scan'
                            }
                            
                            # Generate lock path
                            rel_path = os.path.relpath(file_path, self.cad_root)
                            safe_path = rel_path.replace('\\', '_').replace('/', '_').replace(':', '_')
                            safe_path = safe_path.replace('*', '_').replace('?', '_').replace('"', '_')
                            safe_path = safe_path.replace('<', '_').replace('>', '_').replace('|', '_')
                            lock_filename = f"{safe_path}.lock"
                            lock_path = os.path.join(self.lock_dir, lock_filename)
                            
                            try:
                                with open(lock_path, 'w') as f:
                                    json.dump(lock_data, f, indent=2)
                                
                                self.log_message(f"AUTO-CREATED LOCK: {os.path.basename(file_path)} (opened via SolidWorks)")
                                
                            except Exception as e:
                                self.log_message(f"Error creating auto-lock for {file_path}: {e}")
                        else:
                            # I already have a lock - just update timestamp
                            try:
                                rel_path = os.path.relpath(file_path, self.cad_root)
                                safe_path = rel_path.replace('\\', '_').replace('/', '_').replace(':', '_')
                                safe_path = safe_path.replace('*', '_').replace('?', '_').replace('"', '_')
                                safe_path = safe_path.replace('<', '_').replace('>', '_').replace('|', '_')
                                lock_filename = f"{safe_path}.lock"
                                lock_path = os.path.join(self.lock_dir, lock_filename)
                                
                                if os.path.exists(lock_path):
                                    with open(lock_path, 'r') as f:
                                        lock_data = json.load(f)
                                    
                                    lock_data['last_seen'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    lock_data['auto_created'] = True
                                    
                                    with open(lock_path, 'w') as f:
                                        json.dump(lock_data, f, indent=2)
                                        
                            except Exception as e:
                                self.log_message(f"Error updating lock timestamp: {e}")
                    
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
                
                # Update icon with current counts (show warning if collision detected)
                self.update_icon(warning=collision_detected)
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                self.log_message(f"Monitor error: {e}")
                time.sleep(5)
        
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