# CAD Lock System - Quick Setup Guide
right click and open with
accept read only
make sujre google drive is running
intercept and block saves
psutil pip install watchdog
pip install pystray pillow psutil

naming error where two users have a lock so it creates lock and lock(1)


## 📁 File Overview

### 🖥️ **SERVER (Run on ONE computer only)**
- `dashboard.py` - Web dashboard showing all locks
- Displays lock status at: http://localhost:5000

### 💻 **EACH CAD COMPUTER (Required on every computer doing CAD work)**
- `main.py` - Main lock management script
- `open-cad.bat` - Batch file for opening CAD files with locks

## 🚀 Quick Start

### Server Setup (One Time)
1. Choose one computer to run the dashboard
2. Install Python and Flask: `pip install flask`
3. Run: `python dashboard.py`
4. Dashboard available at: http://localhost:5000

### CAD Computer Setup (Every Computer)
1. Copy `main.py` to each CAD computer
2. Install required packages: `pip install psutil`
3. Update paths in `main.py` if needed
4. Test: `python main.py start-monitor`

## 🎯 Daily Usage

### Option A: Manual (Simple)
```cmd
# Open CAD file with lock check
python main.py open "path\to\file.sldprt"

# When done working
python main.py unlock-all
```

### Option B: Automatic (Recommended)
```cmd
# Start auto-monitor once per day
python main.py start-monitor

# Now just open/close SolidWorks normally
# Locks created/removed automatically!
# Ctrl+C to stop at end of day
```

## 📋 Setup for New CAD Computer

1. **Copy files:**
   - Copy `main.py` to new computer
   - Copy `open-cad.bat` to new computer

2. **Install Python packages:**
   ```cmd
   pip install psutil
   ```

3. **Update file paths in main.py:**
   - Line 7: Lock directory path
   - Line 8: CAD root directory path  
   - Line 9: SolidWorks executable path

4. **Test setup:**
   ```cmd
   python main.py cleanup
   python main.py start-monitor
   ```

5. **Optional - File Association:**
   - Right-click any .sldprt file
   - Choose "Open with" → Browse to `open-cad.bat`
   - Check "Always use this app"
   - Now double-clicking CAD files uses lock system

## 🔧 Commands Reference

```cmd
python main.py start-monitor    # Auto lock/unlock (recommended)
python main.py open "file.sldprt"  # Manual open with lock
python main.py unlock-all       # Remove all your locks
python main.py cleanup 24       # Remove locks older than 24 hours
python main.py check "file.sldprt"  # Check lock status
```

## 🌐 Network Access

Other computers can view the dashboard at:
`http://[server-computer-ip]:5000`

Find server IP: `ipconfig` (Windows) or `ip addr` (Linux)

## 🛠️ Troubleshooting

**Lock not removed when file closed?**
- Use auto-monitor: `python main.py start-monitor`
- Or manually: `python main.py unlock-all`

**Dashboard not showing locks?**
- Check lock directory exists: `G:\Shared drives\Cosmic\Engineering\50 - CAD Data\Locks\`
- Verify all computers use same lock directory path

**SolidWorks won't open?**
- Check SolidWorks path in main.py line 9
- Common path: `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe`

## 📝 File Locations

```
Recommended folder structure:
C:\CAD-Lock\
├── main.py           (on every CAD computer)
├── open-cad.bat      (on every CAD computer)
├── dashboard.py      (on server computer only)
└── README.md         (this file)
```

That's it! 🎉