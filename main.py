import os
import json
import sys
import subprocess
import psutil
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

class CADLockManager:
    def __init__(self):
        self.user = os.getenv('USERNAME') or os.getenv('USER')
        self.computer = os.getenv('COMPUTERNAME') or os.getenv('HOSTNAME')
        self.lock_dir = r"G:\Shared drives\Cosmic\Engineering\50 - CAD Data\Locks"
        self.cad_root = r"G:\Shared drives\Cosmic\Engineering\50 - CAD Data"
        self.solidworks_path = r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe"
        
        # Auto-monitoring
        self.auto_monitor_running = False
        self.monitor_thread = None
        
        # Create lock directory if it doesn't exist
        os.makedirs(self.lock_dir, exist_ok=True)
    
    def is_solidworks_running(self):
        """Check if SolidWorks is running"""
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and 'sldworks' in proc.info['name'].lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    
    def find_open_solidworks_files(self):
        """Find open SolidWorks files by detecting temp files"""
        open_files = set()
        
        try:
            # Walk through CAD directory looking for temp files
            for root, dirs, files in os.walk(self.cad_root):
                for file in files:
                    # SolidWorks creates temp files with ~$ prefix
                    if file.startswith('~$') and any(file.lower().endswith(ext) for ext in ['.sldprt', '.sldasm', '.slddrw']):
                        # The temp file indicates the original file is open
                        original_file = file[2:]  # Remove ~$ prefix
                        original_path = os.path.join(root, original_file)
                        
                        # Check if the original file exists
                        if os.path.exists(original_path):
                            open_files.add(original_path)
                        
        except Exception as e:
            print(f"Error scanning for temp files: {e}")
        
        return open_files
    
    def create_lock(self, file_path, auto_created=False):
        lock_path = self.get_lock_path(file_path)
        
        if os.path.exists(lock_path):
            try:
                with open(lock_path, 'r') as f:
                    lock_data = json.load(f)
                    
                # If it's our lock, update the timestamp
                if lock_data.get('user') == self.user:
                    lock_data['last_seen'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if auto_created:
                        lock_data['auto_created'] = True
                    with open(lock_path, 'w') as f:
                        json.dump(lock_data, f, indent=2)
                    return True
                else:
                    print(f"File locked by {lock_data['user']} on {lock_data['computer']} since {lock_data['timestamp']}")
                    return False
            except:
                pass
        
        lock_data = {
            'user': self.user,
            'computer': self.computer,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'last_seen': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'file': os.path.basename(file_path),
            'original_path': file_path,
            'lock_file': lock_path,
            'auto_created': auto_created,
            'detection_method': 'temp_file' if auto_created else 'manual'
        }
        
        try:
            with open(lock_path, 'w') as f:
                json.dump(lock_data, f, indent=2)
            if auto_created:
                print(f"🔒 Auto-locked: {os.path.basename(file_path)}")
            else:
                print(f"Lock created for {os.path.basename(file_path)}")
            return True
        except Exception as e:
            print(f"Failed to create lock: {e}")
            return False
    
    def remove_lock(self, file_path):
        lock_path = self.get_lock_path(file_path)
        
        if os.path.exists(lock_path):
            try:
                with open(lock_path, 'r') as f:
                    lock_data = json.load(f)
                
                if lock_data.get('user') == self.user or lock_data.get('computer') == self.computer:
                    os.remove(lock_path)
                    if lock_data.get('auto_created'):
                        print(f"🔓 Auto-unlocked: {os.path.basename(file_path)}")
                    else:
                        print(f"Lock removed for: {os.path.basename(file_path)}")
                else:
                    print(f"Cannot remove lock - owned by {lock_data.get('user')}")
            except Exception as e:
                print(f"Error removing lock: {e}")
        else:
            print(f"No lock found for: {os.path.basename(file_path)}")
    
    def check_lock(self, file_path):
        lock_path = self.get_lock_path(file_path)
        
        if os.path.exists(lock_path):
            with open(lock_path, 'r') as f:
                lock_info = json.load(f)
            print(f"Lock Status for: {os.path.basename(file_path)}")
            print(f"Locked by: {lock_info['user']}")
            print(f"Computer: {lock_info['computer']}")
            print(f"Since: {lock_info['timestamp']}")
            print(f"Lock file: {lock_path}")
            return lock_info
        else:
            print(f"No lock found for: {os.path.basename(file_path)}")
            print(f"File is available for editing.")
            return None
    
    def get_lock_path(self, file_path):
        """Generate lock file path in centralized directory"""
        try:
            # Get relative path from CAD root
            rel_path = os.path.relpath(file_path, self.cad_root)
        except ValueError:
            # If file is not under CAD root, use full path
            rel_path = file_path.replace(':', '_').replace('\\', '_').replace('/', '_')
        
        # Replace problematic characters with underscores
        safe_path = rel_path.replace('\\', '_').replace('/', '_').replace(':', '_')
        safe_path = safe_path.replace('*', '_').replace('?', '_').replace('"', '_')
        safe_path = safe_path.replace('<', '_').replace('>', '_').replace('|', '_')
        
        lock_filename = f"{safe_path}.lock"
        return os.path.join(self.lock_dir, lock_filename)
    
    def open_solidworks(self, file_path, read_only=False):
        """Open SolidWorks with the specified file"""
        try:
            if read_only:
                # Open in read-only mode (hidden window)
                subprocess.Popen([self.solidworks_path, "/r", file_path], 
                               creationflags=subprocess.CREATE_NO_WINDOW)
                print(f"Opening in READ-ONLY mode: {os.path.basename(file_path)}")
            else:
                # Open normally (hidden window)
                subprocess.Popen([self.solidworks_path, file_path],
                               creationflags=subprocess.CREATE_NO_WINDOW)
                print(f"Opening normally: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"Error opening SolidWorks: {e}")
            print(f"Verify SolidWorks path: {self.solidworks_path}")
    
    def cleanup_stale_locks(self, max_hours=24, force_cleanup_my_locks=False):
        """Remove old lock files and optionally all auto-created locks"""
        removed_count = 0
        
        if not os.path.exists(self.lock_dir):
            return removed_count
        
        try:
            for lock_file in os.listdir(self.lock_dir):
                if lock_file.endswith('.lock'):
                    lock_path = os.path.join(self.lock_dir, lock_file)
                    try:
                        with open(lock_path, 'r') as f:
                            lock_data = json.load(f)
                        
                        should_remove = False
                        
                        if force_cleanup_my_locks:
                            # Remove all our auto-created locks (for when SolidWorks closes)
                            if (lock_data.get('user') == self.user and 
                                lock_data.get('auto_created', False)):
                                should_remove = True
                        else:
                            # Check if lock is old
                            lock_time = datetime.strptime(lock_data['timestamp'], "%Y-%m-%d %H:%M:%S")
                            age_hours = (datetime.now() - lock_time).total_seconds() / 3600
                            
                            if age_hours > max_hours:
                                should_remove = True
                            
                            # Also remove our auto-locks if corresponding temp file doesn't exist
                            if (lock_data.get('user') == self.user and 
                                lock_data.get('auto_created', False)):
                                original_path = lock_data.get('original_path', '')
                                if original_path:
                                    # Check if temp file still exists
                                    temp_file_path = os.path.join(
                                        os.path.dirname(original_path),
                                        '~$' + os.path.basename(original_path)
                                    )
                                    if not os.path.exists(temp_file_path):
                                        should_remove = True
                        
                        if should_remove:
                            # Only remove if it's our lock or very old
                            if (lock_data.get('user') == self.user or 
                                (datetime.now() - datetime.strptime(lock_data['timestamp'], "%Y-%m-%d %H:%M:%S")).total_seconds() > max_hours * 3600):
                                os.remove(lock_path)
                                removed_count += 1
                                if lock_data.get('auto_created'):
                                    print(f"🔓 Auto-unlocked: {lock_data.get('file', lock_file)}")
                                else:
                                    print(f"🧹 Removed stale lock: {lock_data.get('file', lock_file)}")
                    
                    except (json.JSONDecodeError, KeyError, ValueError, OSError) as e:
                        # Remove corrupted lock files that are ours or very old
                        try:
                            file_age = (time.time() - os.path.getmtime(lock_path)) / 3600
                            if file_age > max_hours:
                                os.remove(lock_path)
                                removed_count += 1
                                print(f"🗑️ Removed corrupted lock: {lock_file}")
                        except:
                            pass
        
        except Exception as e:
            print(f"Error during cleanup: {e}")
        
        return removed_count
    
    def auto_monitor_loop(self):
        """Background thread for automatic lock monitoring"""
        print("🔍 Starting automatic lock monitoring...")
        print(f"Detection method: SolidWorks temp files (~$ prefix)")
        
        while self.auto_monitor_running:
            try:
                if self.is_solidworks_running():
                    # Find currently open files
                    open_files = self.find_open_solidworks_files()
                    
                    # Create locks for open files
                    for file_path in open_files:
                        self.create_lock(file_path, auto_created=True)
                    
                    # Clean up locks for files that are no longer open
                    self.cleanup_stale_locks(max_hours=24, force_cleanup_my_locks=False)
                else:
                    # SolidWorks not running - clean up all our auto-locks
                    removed = self.cleanup_stale_locks(max_hours=0, force_cleanup_my_locks=True)
                    if removed > 0:
                        print(f"🧹 SolidWorks closed - cleaned up {removed} auto-locks")
                
                # Wait before next check
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                print(f"Error in auto-monitor: {e}")
                time.sleep(5)
    
    def start_auto_monitor(self):
        """Start automatic lock monitoring in background"""
        if not self.auto_monitor_running:
            self.auto_monitor_running = True
            self.monitor_thread = threading.Thread(target=self.auto_monitor_loop, daemon=True)
            self.monitor_thread.start()
            print("✅ Auto-monitor started")
            return True
        else:
            print("⚠️ Auto-monitor already running")
            return False
    
    def stop_auto_monitor(self):
        """Stop automatic lock monitoring"""
        if self.auto_monitor_running:
            self.auto_monitor_running = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5)
            # Clean up all our auto-locks
            removed = self.cleanup_stale_locks(max_hours=0, force_cleanup_my_locks=True)
            print(f"🛑 Auto-monitor stopped and cleaned up {removed} locks")
        else:
            print("⚠️ Auto-monitor not running")

def show_usage():
    print("Usage: python main.py <action> [file_path] [options]")
    print("Actions:")
    print("  open           - Check lock and open file (creates manual lock)")
    print("  lock           - Create manual lock for file")
    print("  unlock         - Remove lock for file")
    print("  unlock-all     - Remove ALL locks created by current user")
    print("  cleanup [hrs]  - Remove stale locks older than hrs (default: 24)")
    print("  check          - Check lock status")
    print("  start-monitor  - Start automatic background monitoring")
    print("  stop-monitor   - Stop automatic background monitoring")
    print("\nExamples:")
    print('  python main.py open "G:\\path\\to\\file.sldprt"')
    print('  python main.py check "G:\\path\\to\\file.sldprt"')
    print('  python main.py unlock-all')
    print('  python main.py cleanup 48')
    print('  python main.py start-monitor')
    print("\nAuto-Monitor Features:")
    print("  • Detects open SolidWorks files via temp files (~$ prefix)")
    print("  • Creates/removes locks automatically")
    print("  • Cleans up when SolidWorks closes")
    print("  • Runs in background until stopped")

# Main execution
if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_usage()
        input("\nPress Enter to continue...")
        sys.exit(1)
    
    action = sys.argv[1].lower()
    
    # Actions that don't need a file path
    if action in ["unlock-all", "start-monitor", "stop-monitor"]:
        manager = CADLockManager()
        
        if action == "unlock-all":
            removed = manager.cleanup_stale_locks(max_hours=0, force_cleanup_my_locks=True)
            print(f"Removed {removed} locks for user: {manager.user}")
        elif action == "start-monitor":
            manager.start_auto_monitor()
            try:
                print("🔄 Auto-monitor running... Press Ctrl+C to stop")
                while manager.auto_monitor_running:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Stopping auto-monitor...")
                manager.stop_auto_monitor()
        elif action == "stop-monitor":
            manager.stop_auto_monitor()
        
        time.sleep(2)
        sys.exit(0)
    
    # Cleanup action (optional file path)
    if action == "cleanup":
        hours = 24
        if len(sys.argv) > 2:
            try:
                hours = int(sys.argv[2])
            except ValueError:
                hours = 24
        
        manager = CADLockManager()
        removed = manager.cleanup_stale_locks(max_hours=hours)
        print(f"Removed {removed} stale locks older than {hours} hours")
        time.sleep(2)
        sys.exit(0)
    
    # All other actions need a file path
    if len(sys.argv) < 3:
        show_usage()
        input("\nPress Enter to continue...")
        sys.exit(1)
    
    file_path = sys.argv[2]
    
    # Verify file exists for actions that need it
    if action in ["open", "lock", "check"] and not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        input("\nPress Enter to continue...")
        sys.exit(1)
    
    manager = CADLockManager()
    
    if action == "open":
        # Check if file is locked
        lock_info = manager.check_lock(file_path)
        
        if lock_info and lock_info['user'] != manager.user:
            # File is locked by someone else - open read-only
            manager.open_solidworks(file_path, read_only=True)
        else:
            # File is not locked or locked by current user - create lock and open normally
            if manager.create_lock(file_path, auto_created=False):
                manager.open_solidworks(file_path, read_only=False)
            else:
                # Lock creation failed - open read-only
                manager.open_solidworks(file_path, read_only=True)
                
    elif action == "lock":
        manager.create_lock(file_path, auto_created=False)
        
    elif action == "unlock":
        manager.remove_lock(file_path)
        
    elif action == "check":
        manager.check_lock(file_path)
        
    else:
        print(f"Unknown action: {action}")
        show_usage()
        
    # Keep window open briefly so user can see the output (but hidden)
    if action not in ["start-monitor", "stop-monitor"]:
        time.sleep(1)  # Reduced from 2 seconds and only for non-monitor actions