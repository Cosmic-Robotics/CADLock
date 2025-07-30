import os
import json
import time
from datetime import datetime
from flask import Flask, render_template_string, jsonify
from pathlib import Path
import threading

app = Flask(__name__)

class LockDashboard:
    def __init__(self):
        self.lock_dir = r"G:\Shared drives\Cosmic\Engineering\50 - CAD Data\Locks"
        self.cad_root = r"G:\Shared drives\Cosmic\Engineering\50 - CAD Data"
    
    def get_all_locks(self):
        """Get all current lock files and their information"""
        locks = []
        
        if not os.path.exists(self.lock_dir):
            return locks
        
        try:
            for lock_file in os.listdir(self.lock_dir):
                if lock_file.endswith('.lock'):
                    lock_path = os.path.join(self.lock_dir, lock_file)
                    try:
                        with open(lock_path, 'r') as f:
                            lock_data = json.load(f)
                        
                        # Calculate time since lock was created
                        lock_time = datetime.strptime(lock_data['timestamp'], "%Y-%m-%d %H:%M:%S")
                        time_diff = datetime.now() - lock_time
                        
                        # Format duration
                        hours, remainder = divmod(int(time_diff.total_seconds()), 3600)
                        minutes, seconds = divmod(remainder, 60)
                        
                        if hours > 0:
                            duration = f"{hours}h {minutes}m"
                        elif minutes > 0:
                            duration = f"{minutes}m {seconds}s"
                        else:
                            duration = f"{seconds}s"
                        
                        # Check if original file still exists
                        file_exists = os.path.exists(lock_data.get('original_path', ''))
                        
                        locks.append({
                            'file': lock_data.get('file', 'Unknown'),
                            'user': lock_data.get('user', 'Unknown'),
                            'computer': lock_data.get('computer', 'Unknown'),
                            'timestamp': lock_data.get('timestamp', 'Unknown'),
                            'duration': duration,
                            'original_path': lock_data.get('original_path', ''),
                            'lock_file': lock_file,
                            'file_exists': file_exists,
                            'lock_time_obj': lock_time
                        })
                    
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        # Handle corrupted lock files
                        locks.append({
                            'file': lock_file,
                            'user': 'CORRUPTED',
                            'computer': 'CORRUPTED',
                            'timestamp': 'CORRUPTED',
                            'duration': 'CORRUPTED',
                            'original_path': '',
                            'lock_file': lock_file,
                            'file_exists': False,
                            'lock_time_obj': datetime.now()
                        })
        
        except Exception as e:
            print(f"Error reading lock directory: {e}")
        
        # Sort by lock time (newest first)
        locks.sort(key=lambda x: x['lock_time_obj'], reverse=True)
        return locks
    
    def cleanup_stale_locks(self, max_hours=24):
        """Remove lock files older than specified hours"""
        removed_count = 0
        
        if not os.path.exists(self.lock_dir):
            return removed_count
        
        try:
            for lock_file in os.listdir(self.lock_dir):
                if lock_file.endswith('.lock'):
                    lock_path = os.path.join(self.lock_dir, lock_file)
                    try:
                        # Check file modification time
                        file_time = datetime.fromtimestamp(os.path.getmtime(lock_path))
                        age_hours = (datetime.now() - file_time).total_seconds() / 3600
                        
                        if age_hours > max_hours:
                            os.remove(lock_path)
                            removed_count += 1
                            print(f"Removed stale lock: {lock_file}")
                    
                    except Exception as e:
                        print(f"Error processing {lock_file}: {e}")
        
        except Exception as e:
            print(f"Error during cleanup: {e}")
        
        return removed_count

# Create dashboard instance
lock_manager = LockDashboard()

# HTML template for the dashboard
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CAD Lock Dashboard - Cosmic Engineering</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
            color: white;
            padding: 30px;
            text-align: center;
            position: relative;
        }
        
        .header h1 {
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }
        
        .header .subtitle {
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 1.1em;
        }
        
        .stats {
            display: flex;
            justify-content: space-around;
            background: #ecf0f1;
            padding: 20px;
            border-bottom: 1px solid #bdc3c7;
        }
        
        .stat-item {
            text-align: center;
        }
        
        .stat-number {
            font-size: 2em;
            font-weight: bold;
            color: #2c3e50;
        }
        
        .stat-label {
            color: #7f8c8d;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .refresh-info {
            text-align: center;
            padding: 15px;
            background: #f8f9fa;
            color: #6c757d;
            font-size: 0.9em;
            border-bottom: 1px solid #dee2e6;
        }
        
        .locks-container {
            padding: 20px;
            max-height: 600px;
            overflow-y: auto;
        }
        
        .lock-item {
            background: #ffffff;
            border: 1px solid #e9ecef;
            border-radius: 10px;
            margin-bottom: 15px;
            padding: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }
        
        .lock-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        
        .lock-item.warning {
            border-left: 5px solid #f39c12;
        }
        
        .lock-item.error {
            border-left: 5px solid #e74c3c;
        }
        
        .lock-item.normal {
            border-left: 5px solid #27ae60;
        }
        
        .lock-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .file-name {
            font-size: 1.2em;
            font-weight: bold;
            color: #2c3e50;
            margin: 0;
        }
        
        .duration {
            background: #3498db;
            color: white;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: bold;
        }
        
        .duration.warning {
            background: #f39c12;
        }
        
        .duration.error {
            background: #e74c3c;
        }
        
        .lock-details {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        
        .detail-item {
            display: flex;
            flex-direction: column;
        }
        
        .detail-label {
            font-size: 0.8em;
            color: #7f8c8d;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 5px;
        }
        
        .detail-value {
            color: #2c3e50;
            font-weight: 500;
        }
        
        .file-path {
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            background: #f8f9fa;
            padding: 5px;
            border-radius: 3px;
            word-break: break-all;
        }
        
        .no-locks {
            text-align: center;
            padding: 60px 20px;
            color: #7f8c8d;
        }
        
        .no-locks .icon {
            font-size: 4em;
            margin-bottom: 20px;
        }
        
        .cleanup-section {
            background: #f8f9fa;
            padding: 20px;
            border-top: 1px solid #dee2e6;
            text-align: center;
        }
        
        .cleanup-btn {
            background: #e74c3c;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 1em;
            transition: background 0.3s ease;
        }
        
        .cleanup-btn:hover {
            background: #c0392b;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .refreshing {
            animation: pulse 1s infinite;
        }
    </style>
    <script>
        let refreshInterval;
        
        function startAutoRefresh() {
            refreshInterval = setInterval(refreshData, 30000); // Refresh every 30 seconds
        }
        
        function refreshData() {
            const container = document.querySelector('.container');
            container.classList.add('refreshing');
            
            fetch('/api/locks')
                .then(response => response.json())
                .then(data => {
                    updateDashboard(data);
                    container.classList.remove('refreshing');
                })
                .catch(error => {
                    console.error('Error refreshing data:', error);
                    container.classList.remove('refreshing');
                });
        }
        
        function updateDashboard(data) {
            // Update stats
            document.querySelector('.stat-number').textContent = data.locks.length;
            
            // Update locks list
            const locksContainer = document.querySelector('.locks-container');
            if (data.locks.length === 0) {
                locksContainer.innerHTML = `
                    <div class="no-locks">
                        <div class="icon">🔓</div>
                        <h3>No Files Currently Locked</h3>
                        <p>All CAD files are available for editing</p>
                    </div>
                `;
            } else {
                let html = '';
                data.locks.forEach(lock => {
                    const durationClass = getDurationClass(lock.duration);
                    const itemClass = getItemClass(lock.duration, lock.file_exists);
                    
                    html += `
                        <div class="lock-item ${itemClass}">
                            <div class="lock-header">
                                <h3 class="file-name">${lock.file}</h3>
                                <span class="duration ${durationClass}">${lock.duration}</span>
                            </div>
                            <div class="lock-details">
                                <div class="detail-item">
                                    <span class="detail-label">User</span>
                                    <span class="detail-value">${lock.user}</span>
                                </div>
                                <div class="detail-item">
                                    <span class="detail-label">Computer</span>
                                    <span class="detail-value">${lock.computer}</span>
                                </div>
                                <div class="detail-item">
                                    <span class="detail-label">Locked Since</span>
                                    <span class="detail-value">${lock.timestamp}</span>
                                </div>
                                <div class="detail-item">
                                    <span class="detail-label">File Path</span>
                                    <span class="detail-value file-path">${lock.original_path}</span>
                                </div>
                            </div>
                        </div>
                    `;
                });
                locksContainer.innerHTML = html;
            }
        }
        
        function getDurationClass(duration) {
            if (duration.includes('h') && parseInt(duration) >= 8) return 'error';
            if (duration.includes('h') && parseInt(duration) >= 2) return 'warning';
            return '';
        }
        
        function getItemClass(duration, fileExists) {
            if (!fileExists) return 'error';
            if (duration.includes('h') && parseInt(duration) >= 8) return 'error';
            if (duration.includes('h') && parseInt(duration) >= 2) return 'warning';
            return 'normal';
        }
        
        function cleanupStale() {
            if (confirm('Remove all locks older than 24 hours?')) {
                fetch('/api/cleanup', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        alert(`Removed ${data.removed_count} stale locks`);
                        refreshData();
                    })
                    .catch(error => {
                        console.error('Error during cleanup:', error);
                        alert('Error during cleanup');
                    });
            }
        }
        
        // Start auto-refresh when page loads
        document.addEventListener('DOMContentLoaded', function() {
            startAutoRefresh();
        });
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>CAD Lock Dashboard</h1>
            <p class="subtitle">Cosmic Engineering - Real-time File Lock Monitoring</p>
        </div>
        
        <div class="stats">
            <div class="stat-item">
                <div class="stat-number">{{ locks|length }}</div>
                <div class="stat-label">Active Locks</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">{{ current_time.strftime('%H:%M') }}</div>
                <div class="stat-label">Current Time</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">{{ current_time.strftime('%m/%d') }}</div>
                <div class="stat-label">Date</div>
            </div>
        </div>
        
        <div class="refresh-info">
            🔄 Auto-refreshes every 30 seconds | Last updated: {{ current_time.strftime('%H:%M:%S') }}
        </div>
        
        <div class="locks-container">
            {% if locks %}
                {% for lock in locks %}
                <div class="lock-item {% if not lock.file_exists %}error{% elif lock.duration.split('h')[0]|int >= 8 and 'h' in lock.duration %}error{% elif lock.duration.split('h')[0]|int >= 2 and 'h' in lock.duration %}warning{% else %}normal{% endif %}">
                    <div class="lock-header">
                        <h3 class="file-name">{{ lock.file }}</h3>
                        <span class="duration {% if lock.duration.split('h')[0]|int >= 8 and 'h' in lock.duration %}error{% elif lock.duration.split('h')[0]|int >= 2 and 'h' in lock.duration %}warning{% endif %}">{{ lock.duration }}</span>
                    </div>
                    <div class="lock-details">
                        <div class="detail-item">
                            <span class="detail-label">User</span>
                            <span class="detail-value">{{ lock.user }}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Computer</span>
                            <span class="detail-value">{{ lock.computer }}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Locked Since</span>
                            <span class="detail-value">{{ lock.timestamp }}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">File Path</span>
                            <span class="detail-value file-path">{{ lock.original_path }}</span>
                        </div>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="no-locks">
                    <div class="icon">🔓</div>
                    <h3>No Files Currently Locked</h3>
                    <p>All CAD files are available for editing</p>
                </div>
            {% endif %}
        </div>
        
        <div class="cleanup-section">
            <button class="cleanup-btn" onclick="cleanupStale()">
                🗑️ Cleanup Stale Locks (24h+)
            </button>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    locks = lock_manager.get_all_locks()
    return render_template_string(HTML_TEMPLATE, 
                                locks=locks, 
                                current_time=datetime.now())

@app.route('/api/locks')
def api_locks():
    """API endpoint for getting lock data as JSON"""
    locks = lock_manager.get_all_locks()
    return jsonify({
        'locks': locks,
        'count': len(locks),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/cleanup', methods=['POST'])
def api_cleanup():
    """API endpoint for cleaning up stale locks"""
    removed_count = lock_manager.cleanup_stale_locks(max_hours=24)
    return jsonify({
        'removed_count': removed_count,
        'timestamp': datetime.now().isoformat()
    })

def run_server():
    """Run the Flask server"""
    print("Starting CAD Lock Dashboard...")
    print("Dashboard will be available at: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Server error: {e}")

if __name__ == '__main__':
    run_server()