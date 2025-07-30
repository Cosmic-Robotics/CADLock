import os
import json
import time
import psutil
import threading
from datetime import datetime
from pathlib import Path

class DebugLockMonitor:
    def __init__(self):
        self.lock_dir = r"G:\Shared drives\Cosmic\Engineering\50 - CAD Data\Locks"
        self.cad_root = r"G:\Shared drives\Cosmic\Engineering\50 - CAD Data"
        self.user = os.getenv('USERNAME')
        self.computer = os.getenv('COMPUTERNAME')
        
    def debug_solidworks_processes(self):
        """Debug what SolidWorks processes and files we can detect"""
        print("🔍 DEBUGGING SOLIDWORKS DETECTION")
        print("=" * 50)
        
        sw_processes = []
        
        # Find all SolidWorks processes
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
            try:
                if proc.info['name'] and 'sldworks' in proc.info['name'].lower():
                    sw_processes.append(proc)
                    print(f"📋 Found SolidWorks Process:")
                    print(f"   PID: {proc.info['pid']}")
                    print(f"   Name: {proc.info['name']}")
                    print(f"   Exe: {proc.info['exe']}")
                    print()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if not sw_processes:
            print("❌ No SolidWorks processes found!")
            return
        
        # Check open files for each process
        for proc in sw_processes:
            try:
                process = psutil.Process(proc.info['pid'])
                print(f"🔎 Checking files for PID {proc.info['pid']}:")
                
                open_files = []
                try:
                    for file_handle in process.open_files():
                        file_path = file_handle.path
                        print(f"   📄 Open file: {file_path}")
                        
                        if any(file_path.lower().endswith(ext) for ext in ['.sldprt', '.sldasm', '.slddrw']):
                            if self.cad_root.lower() in file_path.lower():
                                open_files.append(file_path)
                                print(f"   ✅ CAD FILE MATCH: {file_path}")
                
                except psutil.AccessDenied:
                    print(f"   ❌ Access denied to file handles for PID {proc.info['pid']}")
                
                print(f"   🎯 Total CAD files detected: {len(open_files)}")
                for f in open_files:
                    print(f"      • {f}")
                print()
                
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                print(f"   ❌ Error accessing process {proc.info['pid']}: {e}")
                print()
    
    def debug_current_locks(self):
        """Debug current lock files"""
        print("🔒 CURRENT LOCK FILES")
        print("=" * 50)
        
        if not os.path.exists(self.lock_dir):
            print("❌ Lock directory doesn't exist!")
            return
        
        lock_files = [f for f in os.listdir(self.lock_dir) if f.endswith('.lock')]
        
        if not lock_files:
            print("✅ No lock files found")
            return
        
        for lock_file in lock_files:
            lock_path = os.path.join(self.lock_dir, lock_file)
            try:
                with open(lock_path, 'r') as f:
                    lock_data = json.load(f)
                
                print(f"🔐 Lock file: {lock_file}")
                print(f"   User: {lock_data.get('user', 'Unknown')}")
                print(f"   Computer: {lock_data.get('computer', 'Unknown')}")
                print(f"   File: {lock_data.get('file', 'Unknown')}")
                print(f"   Original path: {lock_data.get('original_path', 'Unknown')}")
                print(f"   Timestamp: {lock_data.get('timestamp', 'Unknown')}")
                print(f"   Auto-created: {lock_data.get('auto_created', 'Not specified')}")
                
                # Check if original file exists
                original_path = lock_data.get('original_path')
                if original_path:
                    exists = os.path.exists(original_path)
                    print(f"   File exists: {exists}")
                
                print()
                
            except (json.JSONDecodeError, KeyError) as e:
                print(f"❌ Error reading {lock_file}: {e}")
                print()
    
    def simplified_detection(self):
        """Simplified detection using process names only"""
        print("🎯 SIMPLIFIED DETECTION METHOD")
        print("=" * 50)
        
        # Just check if SolidWorks is running at all
        sw_running = False
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and 'sldworks' in proc.info['name'].lower():
                    sw_running = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        print(f"SolidWorks running: {sw_running}")
        
        # Alternative: Check for recent file access in CAD directory
        recent_files = self.get_recently_accessed_cad_files()
        print(f"Recently accessed CAD files: {len(recent_files)}")
        for f in recent_files:
            print(f"   • {f}")
        
        return sw_running, recent_files
    
    def get_recently_accessed_cad_files(self, minutes=5):
        """Get CAD files accessed in the last N minutes"""
        recent_files = []
        cutoff_time = time.time() - (minutes * 60)
        
        try:
            for root, dirs, files in os.walk(self.cad_root):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in ['.sldprt', '.sldasm', '.slddrw']):
                        file_path = os.path.join(root, file)
                        try:
                            # Check last access time
                            access_time = os.path.getatime(file_path)
                            if access_time > cutoff_time:
                                recent_files.append(file_path)
                        except OSError:
                            continue
        except Exception as e:
            print(f"Error checking recent files: {e}")
        
        return recent_files
    
    def run_debug_session(self):
        """Run a complete debug session"""
        while True:
            print(f"\n🕐 DEBUG SESSION - {datetime.now().strftime('%H:%M:%S')}")
            print("=" * 60)
            
            self.debug_solidworks_processes()
            self.debug_current_locks()
            self.simplified_detection()
            
            print("\n⏳ Waiting 15 seconds for next check...")
            print("Press Ctrl+C to stop debugging")
            print("=" * 60)
            
            try:
                time.sleep(15)
            except KeyboardInterrupt:
                print("\n👋 Debug session stopped")
                break

def main():
    print("🐛 CAD Lock Debug Tool")
    print("This will help diagnose why auto-locking isn't working")
    print()
    print("Instructions:")
    print("1. Start this debug tool")
    print("2. Open a CAD file in SolidWorks")
    print("3. Watch the debug output")
    print("4. Close the CAD file")
    print("5. Watch what happens")
    print()
    input("Press Enter to start debugging...")
    
    monitor = DebugLockMonitor()
    monitor.run_debug_session()

if __name__ == "__main__":
    main()