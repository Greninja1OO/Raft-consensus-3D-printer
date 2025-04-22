from flask import Flask, render_template, request, redirect, url_for, flash
import requests
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Required for flash messages

# Welcome server URL
WELCOME_SERVER_URL = "http://127.0.0.1:5100"

def get_client():
    """Get status and connection info from welcome server"""
    try:
        response = requests.get(f"{WELCOME_SERVER_URL}/NodeStatus")
        return response.json() if response.status_code == 200 else None
    except requests.RequestException:
        return None

def make_api_request(method, endpoint, data=None):
    """Make API request through welcome server proxy"""
    try:
        url = f"{WELCOME_SERVER_URL}/proxy/{endpoint}"
        if method == "GET":
            response = requests.get(url)
        else:
            response = requests.request(method, url, json=data)
        return response.json() if response.status_code == 200 else None
    except requests.RequestException:
        return None

@app.route('/')
def index():
    """Dashboard page"""
    status = get_client()
    printers = make_api_request("GET", "api/v1/printers") or []
    jobs = make_api_request("GET", "api/v1/jobs") or []
    filaments = make_api_request("GET", "api/v1/filaments") or []
    
    # Calculate statistics
    active_jobs = sum(1 for job in jobs if job['status'] in ['Queued', 'Running'])
    available_printers = sum(1 for printer in printers)
    filament_stats = {
        'total': len(filaments),
        'low': sum(1 for f in filaments if f.get('remaining_weight', 0) < 100)  # Less than 100g
    }
    
    return render_template('index.html',
                         status=status,
                         printers=printers,
                         jobs=jobs,
                         filaments=filaments,
                         active_jobs=active_jobs,
                         available_printers=available_printers,
                         filament_stats=filament_stats)

@app.route('/printers')
def printers():
    """Printers management page"""
    printers = make_api_request("GET", "api/v1/printers") or []
    return render_template('printers.html', printers=printers)

@app.route('/add_printer', methods=['POST'])
def add_printer():
    """Add a new printer"""
    data = {
        'id': request.form['printer_id'],
        'company': request.form['company'],
        'model': request.form['model']
    }
    response = make_api_request("POST", "api/v1/printers", data)
    if response and response.get('success'):
        flash('Printer added successfully!', 'success')
    else:
        flash('Failed to add printer.', 'error')
    return redirect(url_for('printers'))

@app.route('/filaments')
def filaments():
    """Filaments management page"""
    filaments = make_api_request("GET", "api/v1/filaments") or []
    return render_template('filaments.html', filaments=filaments)

@app.route('/add_filament', methods=['POST'])
def add_filament():
    """Add a new filament"""
    data = {
        'id': request.form['filament_id'],
        'type': request.form['type'].upper(),
        'color': request.form['color'],
        'total_weight_in_grams': float(request.form['weight']),
        'remaining_weight_in_grams': float(request.form['weight'])
    }
    response = make_api_request("POST", "api/v1/filaments", data)
    if response and response.get('success'):
        flash('Filament added successfully!', 'success')
    else:
        flash('Failed to add filament.', 'error')
    return redirect(url_for('filaments'))

@app.route('/jobs')
def jobs():
    """Jobs management page"""
    all_jobs = make_api_request("GET", "api/v1/jobs") or []
    printers = make_api_request("GET", "api/v1/printers") or []
    filaments = make_api_request("GET", "api/v1/filaments") or []
    return render_template('jobs.html', 
                         jobs=all_jobs, 
                         printers=printers,
                         filaments=filaments)

@app.route('/add_job', methods=['POST'])
def add_job():
    """Add a new print job"""
    data = {
        'id': request.form['job_id'],
        'printer_id': request.form['printer_id'],
        'filament_id': request.form['filament_id'],
        'filepath': request.form['filepath'],
        'print_weight_in_grams': float(request.form['print_weight'])
    }
    response = make_api_request("POST", "api/v1/jobs", data)
    if response and response.get('success'):
        flash('Job added successfully!', 'success')
    else:
        flash('Failed to add job.', 'error')
    return redirect(url_for('jobs'))

@app.route('/update_job_status', methods=['POST'])
def update_job_status():
    """Update job status"""
    job_id = request.form['job_id']
    new_status = request.form['status']
    response = make_api_request("PATCH", f"api/v1/jobs/{job_id}/status", {'status': new_status})
    if response and response.get('success'):
        flash('Job status updated successfully!', 'success')
    else:
        flash('Failed to update job status.', 'error')
    return redirect(url_for('jobs'))

@app.route('/cluster')
def cluster():
    """Cluster status page"""
    status = get_client()
    return render_template('cluster.html', status=status)

@app.template_filter('datetime')
def format_datetime(timestamp):
    """Format timestamp for templates"""
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    return timestamp

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5200, debug=True)