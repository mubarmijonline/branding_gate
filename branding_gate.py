from flask import Flask, render_template, request, url_for, redirect, flash, session, app,jsonify,make_response,send_file,send_from_directory,abort, current_app
from functools import wraps
#from dbconnection import connection
import MySQLdb
#from flask_pymongo import PyMongo
#from pymongo import MongoClient
#import pymongo
import gc
import csv  
import json
import sys
import datetime
import time
import os
from datetime import timedelta, datetime
import re
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
import rbac
import zipfile
import ssl
import shutil
from io import StringIO
import random
import glob
import calendar
from importlib import reload
reload(sys)
from flask_mail import Mail, Message
import pandas as pd
from pandas import ExcelWriter
from pandas import ExcelFile
import xlrd
import traceback

import threading
import numpy as np
from flask_cors import CORS

import MySQLdb.cursors

from negotiation_workflow import InvalidNegotiationTransition, transition

# PDF generation imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from io import BytesIO

def connection():
    conn = MySQLdb.connect(
        host="localhost",
        user="ps",
        passwd="Aa@123456",
        db='branding_gate',
        port=3306,
        charset='utf8mb4',
        use_unicode=True,
        init_command='SET NAMES UTF8',
    )
    cur = conn.cursor(MySQLdb.cursors.DictCursor)
    return conn, cur

def initialize_default_templates():
    """
    Initialize default request type templates in the database.
    Checks if templates exist and adds any missing ones.
    This ensures the system always has the base templates available.
    
    Tables used:
    - request_type: stores template definitions (id, code, name, template_code)
    - template_field_def: stores field definitions for each template
    """
    try:
        conn, cur = connection()
        
        # Check if required tables exist
        cur.execute("""
            SELECT COUNT(*) as table_exists
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = 'request_type'
        """)
        request_type_check = cur.fetchone()
        
        cur.execute("""
            SELECT COUNT(*) as table_exists
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = 'template_field_def'
        """)
        template_field_check = cur.fetchone()
        
        if not request_type_check or request_type_check['table_exists'] == 0:
            print("⚠ request_type table does not exist - skipping template initialization")
            cur.close()
            conn.close()
            return {'success': False, 'error': 'request_type table not found'}
            
        if not template_field_check or template_field_check['table_exists'] == 0:
            print("⚠ template_field_def table does not exist - skipping template initialization")
            cur.close()
            conn.close()
            return {'success': False, 'error': 'template_field_def table not found'}
        
        print("=== Starting Default Templates Initialization ===")
        
        # Check which templates already exist in request_type table
        cur.execute("SELECT template_code FROM request_type WHERE template_code IS NOT NULL")
        existing_templates = {row['template_code'] for row in cur.fetchall()}
        print(f"Found {len(existing_templates)} existing templates: {existing_templates}")
        
        templates_added = 0
        templates_skipped = 0
        
        # Define templates to check/add (we'll add them in chunks)
        templates_to_check = ['t1', 't2', 't3', 't4', 't5']
        
        for template_code in templates_to_check:
            if template_code in existing_templates:
                print(f"✓ Template {template_code} already exists - skipping")
                templates_skipped += 1
            else:
                print(f"⚠ Template {template_code} is missing")
        
        cur.close()
        conn.close()
        
        print(f"\n=== Template Check Complete ===")
        print(f"Templates found: {templates_skipped}")
        print(f"Templates missing: {len(templates_to_check) - templates_skipped}")
        
        # Now add missing templates one by one
        if templates_skipped < len(templates_to_check):
            templates_added = add_missing_templates(existing_templates)
        
        return {
            'success': True,
            'templates_added': templates_added,
            'templates_skipped': templates_skipped,
            'total': len(templates_to_check)
        }
        
    except Exception as e:
        print(f"ERROR in initialize_default_templates: {e}")
        print(f"Full traceback: {traceback.format_exc()}")
        return {
            'success': False,
            'error': str(e)
        }

def add_missing_templates(existing_templates):
    """Add missing templates one by one to avoid memory issues"""
    templates_added = 0
    
    # Template 1: Event & Booth
    if 't1' not in existing_templates:
        if add_event_booth_template():
            templates_added += 1
    
    # Template 2: Production & Printing
    if 't2' not in existing_templates:
        if add_production_printing_template():
            templates_added += 1
    
    # Template 3: Digital Marketing
    if 't3' not in existing_templates:
        if add_digital_marketing_template():
            templates_added += 1
    
    # Template 4: Transfers & Logistics
    if 't4' not in existing_templates:
        if add_transfers_logistics_template():
            templates_added += 1
    
    # Template 5: General Services
    if 't5' not in existing_templates:
        if add_general_services_template():
            templates_added += 1
    
    return templates_added

def add_event_booth_template():
    """Add Event & Booth template (t1)"""
    try:
        conn, cur = connection()
        
        # Insert into request_type table
        cur.execute("""
            INSERT INTO request_type 
            (code, name, template_code, active)
            VALUES ('EVENT_BOOTH', 'Event & Booth', 't1', 1)
        """)
        
        # Add fields to template_field_def
        fields = [

            ('event_name', 'Event Name', 'text', 1, 3),
            ('event_type', 'Event Type', 'text', 1, 4),
            ('event_date', 'Event Date', 'date', 1, 5),
            ('event_end_date', 'Event End Date', 'date', 0, 6),
            ('event_duration', 'Event Duration (Days)', 'number', 1, 7),
            ('event_location', 'Event Location/Venue', 'text', 1, 8),

            ('attendees_expected', 'Expected Attendees', 'number', 0, 10),
            ('special_requirements', 'Special Requirements', 'textarea', 0, 11),
             ('dismantle_date', 'Dismantle Date', 'date', 0, 12)
        ]
        
        for field_key, label, data_type, required, sort_order in fields:
            cur.execute("""
                INSERT INTO template_field_def
                (template_code, field_key, label, data_type, required, sort_order)
                VALUES ('t1', %s, %s, %s, %s, %s)
            """, (field_key, label, data_type, required, sort_order))
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"✓ Added template t1 (Event & Booth Template) with {len(fields)} fields")
        return True
    except Exception as e:
        print(f"✗ Error adding template t1: {e}")
        print(f"  Traceback: {traceback.format_exc()}")
        return False

def add_production_printing_template():
    """Add Production & Printing template (t2)"""
    try:
        conn, cur = connection()
        
        # Insert into request_type table
        cur.execute("""
            INSERT INTO request_type 
            (code, name, template_code, active)
            VALUES ('PRODUCTION_PRINTING', 'Production & Printing', 't2', 1)
        """)
        
        # Add fields to template_field_def
        fields = [

            ('production_type', 'Production/Print Type', 'text', 1, 3),
            ('quantity', 'Quantity', 'number', 1, 4),
            ('material_specs', 'Material Specifications', 'textarea', 1, 5),
            ('delivery_date', 'Required Delivery Date', 'date', 1, 7),
            ('finishing_requirements', 'Finishing Requirements', 'textarea', 0, 8)
        ]
        
        for field_key, label, data_type, required, sort_order in fields:
            cur.execute("""
                INSERT INTO template_field_def
                (template_code, field_key, label, data_type, required, sort_order)
                VALUES ('t2', %s, %s, %s, %s, %s)
            """, (field_key, label, data_type, required, sort_order))
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"✓ Added template t2 (Production & Printing Template) with {len(fields)} fields")
        return True
    except Exception as e:
        print(f"✗ Error adding template t2: {e}")
        print(f"  Traceback: {traceback.format_exc()}")
        return False

def add_digital_marketing_template():
    """Add Digital Marketing template (t3)"""
    try:
        conn, cur = connection()
        
        # Insert into request_type table
        cur.execute("""
            INSERT INTO request_type 
            (code, name, template_code, active)
            VALUES ('DIGITAL_MARKETING', 'Digital Marketing', 't3', 1)
        """)
        
        # Add fields to template_field_def
        fields = [

            ('campaign_name', 'Campaign Name', 'text', 1, 3),
            ('campaign_type', 'Campaign Type', 'text', 1, 4),
            ('platforms', 'Platforms/Channels', 'text', 1, 5),
            ('campaign_start_date', 'Campaign Start Date', 'date', 1, 6),
            ('campaign_end_date', 'Campaign End Date', 'date', 1, 7),
            ('campaign_duration', 'Campaign Duration (Days)', 'number', 1, 8),
            ('target_audience', 'Target Audience', 'textarea', 1, 9),
            ('campaign_objectives', 'Campaign Objectives', 'textarea', 1, 10)
        ]
        
        for field_key, label, data_type, required, sort_order in fields:
            cur.execute("""
                INSERT INTO template_field_def
                (template_code, field_key, label, data_type, required, sort_order)
                VALUES ('t3', %s, %s, %s, %s, %s)
            """, (field_key, label, data_type, required, sort_order))
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"✓ Added template t3 (Digital Marketing Template) with {len(fields)} fields")
        return True
    except Exception as e:
        print(f"✗ Error adding template t3: {e}")
        print(f"  Traceback: {traceback.format_exc()}")
        return False

def add_transfers_logistics_template():
    """Add Transfers & Logistics template (t4)"""
    try:
        conn, cur = connection()
        
        # Insert into request_type table
        cur.execute("""
            INSERT INTO request_type 
            (code, name, template_code, active)
            VALUES ('TRANSFERS_LOGISTICS', 'Transfers & Logistics', 't4', 1)
        """)
        
        # Add fields to template_field_def
        fields = [

            ('transfer_type', 'Transfer/Logistics Type', 'text', 1, 3),
            ('pickup_location', 'Pickup Location', 'text', 1, 4),
            ('delivery_location', 'Delivery Location', 'text', 1, 5),
            ('pickup_date', 'Pickup Date', 'date', 1, 6),
            ('delivery_date', 'Delivery Date', 'date', 1, 7),
            ('items_description', 'Items/Assets Description', 'textarea', 1, 8),
            ('special_handling', 'Special Handling Requirements', 'textarea', 0, 9)
        ]
        
        for field_key, label, data_type, required, sort_order in fields:
            cur.execute("""
                INSERT INTO template_field_def
                (template_code, field_key, label, data_type, required, sort_order)
                VALUES ('t4', %s, %s, %s, %s, %s)
            """, (field_key, label, data_type, required, sort_order))
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"✓ Added template t4 (Transfers & Logistics Template) with {len(fields)} fields")
        return True
    except Exception as e:
        print(f"✗ Error adding template t4: {e}")
        print(f"  Traceback: {traceback.format_exc()}")
        return False

def add_general_services_template():
    """Add General Services template (t5)"""
    try:
        conn, cur = connection()
        
        # Insert into request_type table
        cur.execute("""
            INSERT INTO request_type 
            (code, name, template_code, active)
            VALUES ('GENERAL_SERVICES', 'General Services', 't5', 1)
        """)
        
        # Add fields to template_field_def
        fields = [

            ('service_type', 'Service Type', 'text', 1, 3),
            ('service_description', 'Service Description', 'textarea', 1, 4),
            ('start_date', 'Start Date', 'date', 1, 5),
            ('end_date', 'End Date', 'date', 0, 6),
            ('duration', 'Duration (Days)', 'number', 0, 7),
            ('deliverables', 'Expected Deliverables', 'textarea', 1, 8),
            ('additional_notes', 'Additional Notes', 'textarea', 0, 9)
        ]
        
        for field_key, label, data_type, required, sort_order in fields:
            cur.execute("""
                INSERT INTO template_field_def
                (template_code, field_key, label, data_type, required, sort_order)
                VALUES ('t5', %s, %s, %s, %s, %s)
            """, (field_key, label, data_type, required, sort_order))
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"✓ Added template t5 (General Services Template) with {len(fields)} fields")
        return True
    except Exception as e:
        print(f"✗ Error adding template t5: {e}")
        print(f"  Traceback: {traceback.format_exc()}")
        return False

def validate_file_size(file, max_size_mb=20):
    """Validate file size - returns True if valid, False if too large"""
    max_size_bytes = max_size_mb * 1024 * 1024  # Convert MB to bytes
    
    # Get file size by seeking to the end
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to beginning
    
    return file_size <= max_size_bytes

# Request type validation rules
REQUEST_TYPE_RULES = {
    'Event': {
        'required': ['venue', 'attendees_expected'],
        'optional': ['city', 'av_required', 'catering_required', 'permits_required', 'setup_requirements'],
        'description': 'Event management and coordination'
    },
    'Booth': {
        'required': ['booth_size', 'build_type'],
        'optional': ['power_requirements', 'branding_assets', 'materials_needed'],
        'description': 'Exhibition booth design and construction'
    },
    'Activation': {
        'required': ['target_segment', 'promoters_count'],
        'optional': ['locations', 'schedule', 'kpis', 'campaign_duration'],
        'description': 'Brand activation and promotional campaigns'
    },
    'Media': {
        'required': ['media_type', 'duration_days'],
        'optional': ['specs', 'booking_window', 'target_audience'],
        'description': 'Media planning and buying'
    },
    'Design': {
        'required': [],
        'optional': ['design_type', 'dimensions', 'format', 'brand_guidelines'],
        'description': 'Graphic design and creative services'
    },
    'Printing': {
        'required': ['quantity'],
        'optional': ['material', 'finish', 'size', 'delivery_location'],
        'description': 'Printing and production services'
    },
    'Logistics': {
        'required': ['delivery_date'],
        'optional': ['pickup_location', 'delivery_location', 'special_handling'],
        'description': 'Logistics and delivery services'
    },
    'General': {
        'required': [],
        'optional': [],
        'description': 'General service requests'
    }
}

def run_sales_request_migration():
    """Run database migration for sales request revamp"""
    try:
        conn, cur = connection()
        
        print("Starting sales request migration...")
        
        # Step 1: Create main sales_request table
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sales_request (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    client_id INT NOT NULL,
                    request_type VARCHAR(50) NOT NULL DEFAULT 'General',
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    priority ENUM('low', 'normal', 'high', 'urgent') DEFAULT 'normal',
                    start_date DATE NOT NULL,
                    end_date DATE,
                    status ENUM('draft', 'submitted', 'approved', 'in_progress', 'completed', 'cancelled') DEFAULT 'submitted',
                    budget_total DECIMAL(12,2),
                    currency VARCHAR(10) DEFAULT 'EGP',
                    request_data JSON,
                    created_by VARCHAR(100) NOT NULL,
                    modified_by VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    total_cost DECIMAL(12,2),
                    total_sell DECIMAL(12,2),
                    sales_added_date TIMESTAMP,
                    items_count INT DEFAULT 0,
                    
                    FOREIGN KEY (client_id) REFERENCES client(id) ON DELETE CASCADE,
                    INDEX idx_request_type_status (request_type, status),
                    INDEX idx_client_created (client_id, created_at),
                    INDEX idx_status_created (status, created_at)
                )
            """)
            print("✓ sales_request table created/verified")
        except Exception as e:
            print(f"Warning creating sales_request table: {e}")
        
        # Step 2: Create sales_request_items table
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sales_request_items (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    request_id INT NOT NULL,
                    item_type VARCHAR(50) DEFAULT 'general',
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    qty DECIMAL(10,2) NOT NULL DEFAULT 1,
                    unit VARCHAR(20) DEFAULT 'pcs',
                    unit_price DECIMAL(12,2),
                    total DECIMAL(12,2) GENERATED ALWAYS AS (qty * COALESCE(unit_price, 0)) STORED,
                    attributes JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (request_id) REFERENCES sales_request(id) ON DELETE CASCADE,
                    INDEX idx_request_items (request_id),
                    INDEX idx_item_type (item_type)
                )
            """)
            print("✓ sales_request_items table created/verified")
        except Exception as e:
            print(f"Warning creating sales_request_items table: {e}")
            
        # Step 3: Create sales_request_files table  
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sales_request_files (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    request_id INT NOT NULL,
                    file_name VARCHAR(255) NOT NULL,
                    file_path VARCHAR(500) NOT NULL,
                    file_size INT NOT NULL,
                    uploaded_by INT,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (request_id) REFERENCES sales_request(id) ON DELETE CASCADE,
                    FOREIGN KEY (uploaded_by) REFERENCES user(id) ON DELETE SET NULL,
                    INDEX idx_request_files (request_id)
                )
            """)
            print("✓ sales_request_files table created/verified")
        except Exception as e:
            print(f"Warning creating sales_request_files table: {e}")
            
        # Step 4: Create sales_request_status_history table
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sales_request_status_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    request_id INT NOT NULL,
                    old_status VARCHAR(50),
                    new_status VARCHAR(50) NOT NULL,
                    changed_by VARCHAR(100) NOT NULL,
                    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    note TEXT,
                    
                    FOREIGN KEY (request_id) REFERENCES sales_request(id) ON DELETE CASCADE,
                    INDEX idx_request_history (request_id, changed_at)
                )
            """)
            print("✓ sales_request_status_history table created/verified")
        except Exception as e:
            print(f"Warning creating sales_request_status_history table: {e}")
            
        # Step 5: Create type-specific tables
        type_tables = [
            ("event_details", """
                CREATE TABLE IF NOT EXISTS event_details (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    request_id INT NOT NULL UNIQUE,
                    venue VARCHAR(255),
                    city VARCHAR(100),
                    attendees_expected INT,
                    av_required BOOLEAN DEFAULT FALSE,
                    catering_required BOOLEAN DEFAULT FALSE,
                    permits_required BOOLEAN DEFAULT FALSE,
                    setup_requirements TEXT,
                    
                    FOREIGN KEY (request_id) REFERENCES sales_request(id) ON DELETE CASCADE
                )
            """),
            ("booth_details", """
                CREATE TABLE IF NOT EXISTS booth_details (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    request_id INT NOT NULL UNIQUE,
                    booth_size VARCHAR(50),
                    build_type VARCHAR(50),
                    power_requirements VARCHAR(100),
                    branding_assets TEXT,
                    materials_needed TEXT,
                    
                    FOREIGN KEY (request_id) REFERENCES sales_request(id) ON DELETE CASCADE
                )
            """),
            ("activation_details", """
                CREATE TABLE IF NOT EXISTS activation_details (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    request_id INT NOT NULL UNIQUE,
                    target_segment VARCHAR(100),
                    locations JSON,
                    promoters_count INT,
                    schedule JSON,
                    kpis JSON,
                    campaign_duration INT,
                    
                    FOREIGN KEY (request_id) REFERENCES sales_request(id) ON DELETE CASCADE
                )
            """),
            ("media_details", """
                CREATE TABLE IF NOT EXISTS media_details (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    request_id INT NOT NULL UNIQUE,
                    media_type ENUM('OOH', 'TV', 'Digital', 'Print', 'Radio') NOT NULL,
                    specs JSON,
                    duration_days INT,
                    booking_window VARCHAR(100),
                    target_audience VARCHAR(200),
                    
                    FOREIGN KEY (request_id) REFERENCES sales_request(id) ON DELETE CASCADE
                )
            """)
        ]
        
        for table_name, table_sql in type_tables:
            try:
                cur.execute(table_sql)
                print(f"✓ {table_name} table created/verified")
            except Exception as e:
                print(f"Warning creating {table_name} table: {e}")
        
        conn.commit()
        print("✓ Sales request migration completed successfully")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Migration error: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")

def validate_request_type_data(request_type, request_data):
    """Validate request type specific data"""
    if request_type not in REQUEST_TYPE_RULES:
        return False, f"Invalid request type: {request_type}"
    
    rules = REQUEST_TYPE_RULES[request_type]
    
    print(f"DEBUG: Validating {request_type} request_data: {request_data}")
    print(f"DEBUG: Required fields for {request_type}: {rules['required']}")
    
    # Check required fields
    for field in rules['required']:
        field_value = request_data.get(field)
        print(f"DEBUG: Checking field '{field}': value = '{field_value}'")
        if field not in request_data or not request_data[field]:
            print(f"DEBUG: Validation FAILED for field '{field}'")
            return False, f"Required field '{field}' is missing for {request_type} request"
    
    print(f"DEBUG: Validation PASSED for {request_type}")
    return True, "Valid"
#import pytesseract
#from skimage import io, color, filters
#from PIL import Image, ImageEnhance
#import cv2
#from google.cloud import vision
#pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
#from signal import signal, SIGPIPE, SIG_DFL
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./brandinggate-7c1f6-firebase-adminsdk-fbsvc-4e17fc4c74.json"



import requests

#import convert_numbers

#from time_handling import time_add_for_branch_single_date
import firebase_admin

from firebase_admin import credentials,firestore, auth, messaging, firestore
from urllib.parse import quote
import google.auth
from google.auth.transport.requests import Request
from google.auth import impersonated_credentials
cred = credentials.Certificate("./brandinggate-7c1f6-firebase-adminsdk-fbsvc-4e17fc4c74.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
app = Flask(__name__)
CORS(app)
#Bootst/projects/psCalc/templatesrap(app)
app.secret_key = "branding gate api secret key"

# Set maximum file upload size to 25MB (allowing a small buffer over our 20MB limit)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024

################ MAIL CONFIGURATIONS ########################
app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT'] = 465
#app.config['MAIL_USERNAME'] = 'mubarmij1@gmail.com'
#app.config['MAIL_PASSWORD'] = 'esvgidegiwgwggwq'

app.config['MAIL_USERNAME'] = 'noreply.el.time@gmail.com'
app.config['MAIL_PASSWORD'] = 'qluzzjvoshsachqb'

app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
mail = Mail(app)

############### END OF MAIL CONFIGURATIONS ##################

token_verify = "Jjz@8i1hvyp"

"""@app.before_request
def before_request():
    #print("Wakanda")
    #print(request.endpoint)
    #token = request.args['token']
    if 'verification_token' not in request.args and '' :

        #print(request.headers)
        print(request.endpoint)
        #print(request.method)
        #print(request.data)
        session.clear()

        return "404 error",404"""


def initialize_firebase():
    """Initialize Firebase Admin SDK."""
    service_account_file = './eltime-6571b-firebase-adminsdk-71oq0-1b7a4414ce.json'
    if not firebase_admin._apps:  # Prevent reinitialization
        cred = credentials.Certificate(service_account_file)
        firebase_admin.initialize_app(cred)
        print("Firebase initialized successfully.")

def get_user_roles(user_id):
    """
    Return the user's role as a single-element list.

    Kept as a list because templates and the refresh endpoint still read
    session['roles']; authorization itself now runs off session['perms'].
    """
    conn, cur = connection()
    cur.execute("""
        SELECT r.code FROM user u
        JOIN rbac_role r ON r.id = u.rbac_role_id
        WHERE u.id = %s
    """, (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return [row['code']] if row else []


# ---------------------------------------------------------------------------
# RBAC: database and request-scoped wrappers around the pure policy in rbac.py
# ---------------------------------------------------------------------------

def load_permissions(user_id):
    """
    Return (permissions, role_code) for a user, where permissions maps a
    permission code to the scope it is held at. An unassigned user gets ({}, None)
    and is therefore denied everything.
    """
    conn, cur = connection()
    cur.execute("SELECT is_pricing FROM user WHERE id = %s", (user_id,))
    account = cur.fetchone()
    is_pricing = bool(account and account['is_pricing'])

    cur.execute("""
        SELECT r.code AS role_code, rp.permission_code, rp.scope
        FROM user u
        JOIN rbac_role r ON r.id = u.rbac_role_id
        LEFT JOIN role_permission rp ON rp.role_id = r.id
        WHERE u.id = %s
    """, (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    role_code = rows[0]['role_code'] if rows else None
    perms = {row['permission_code']: row['scope'] for row in rows if row['permission_code']}

    # The pricing flag grants pricing on top of the role, so an account with no
    # role at all still gets pricing if it is flagged.
    if is_pricing:
        perms = rbac.apply_pricing_flag(perms)

    return perms, role_code


def has(code):
    """True when the current session holds the permission at any scope."""
    return rbac.resolve(session.get('perms') or {}, code) is not None


def visible_user_ids(code):
    """
    Owner ids the caller may see for this permission.

    Returns None when the scope is unrestricted, so callers can skip building a
    predicate. Aborts 403 when the permission is not held at all.
    """
    scope = rbac.resolve(session.get('perms') or {}, code)
    if scope is None:
        abort(403)
    if scope == 'all':
        return None

    me = session.get('user_id')
    if scope == 'own':
        return [me]

    # Only team and department scope need a lookup.
    conn, cur = connection()
    if scope == 'team':
        cur.execute("SELECT id FROM user WHERE manager_id = %s", (me,))
        others = [row['id'] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return rbac.allowed_user_ids('team', me, direct_report_ids=others)

    cur.execute("""
        SELECT id FROM user
        WHERE department_id IS NOT NULL
          AND department_id = (SELECT department_id FROM user WHERE id = %s)
    """, (me,))
    others = [row['id'] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return rbac.allowed_user_ids('department', me, department_member_ids=others)


def scope_clause(code, column):
    """
    Build a SQL fragment restricting `column` to the owner ids the caller may
    see. Returns ("", []) when the caller's scope is unrestricted.

    Usage:  clause, params = scope_clause('sales_request.view', 'sr.owner_user_id')
            cur.execute("SELECT ... WHERE 1=1 " + clause, [...] + params)
    """
    ids = visible_user_ids(code)
    if ids is None:
        return "", []
    if not ids:
        # Holds the permission but can see nobody; must not degrade to "all".
        return " AND 1=0", []
    placeholders = ",".join(["%s"] * len(ids))
    return " AND %s IN (%s)" % (column, placeholders), list(ids)


def assert_scope(code, owner_user_id):
    """Abort 403 unless the caller's scope covers this record's owner."""
    ids = visible_user_ids(code)
    if ids is not None and owner_user_id not in ids:
        abort(403)


def perm(*codes):
    """
    Decorator gating a route on one or more permissions, any of which suffices.
    Sets `_perms` on the wrapper so the default-deny backstop can see the gate.
    """
    for code in codes:
        if code not in rbac.PERMISSIONS:
            raise rbac.UnknownPermission(code)

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('user_id'):
                if request.path.startswith('/api/'):
                    return jsonify(error='Not authenticated'), 401
                return redirect(url_for('login'))
            if any(has(code) for code in codes):
                return f(*args, **kwargs)
            if request.path.startswith('/api/'):
                return jsonify(error='Forbidden'), 403
            return abort(403)
        decorated_function._perms = codes
        return decorated_function
    return decorator


# Coarse notification audiences, expressed as the permission that defines them.
NOTIFICATION_AUDIENCE = {
    'admin': 'user.create',
    'sales': 'sales_request.create',
    'operation': 'sales_item.cost',
    'pricing': 'sales_item.price',
    'finance': 'finance_txn.approve',
    'sales_head': 'negotiation.decide_sales_head',
}


def get_users_by_role(role_name):
    """
    Return user ids to notify for a workflow role.

    The legacy `role` table is gone; notification call sites still speak in
    coarse terms ('admin', 'sales', 'operation'), so map those onto the
    permission that actually defines the audience.
    """
    permission = NOTIFICATION_AUDIENCE.get(role_name)
    if not permission:
        return []
    role_codes = [code for code, grants in rbac.SEED_MATRIX.items() if permission in grants]
    if not role_codes:
        return []
    conn, cur = connection()
    placeholders = ",".join(["%s"] * len(role_codes))
    cur.execute(
        "SELECT u.id FROM user u JOIN rbac_role r ON r.id = u.rbac_role_id "
        "WHERE r.code IN (%s)" % placeholders,
        role_codes,
    )
    user_ids = [row['id'] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return user_ids


def send_notification_to_role(role_name, title, content):
    """
    Send notification to all users with the specified role.
    """
    try:
        user_ids = get_users_by_role(role_name)
        added_by = session.get('name', 'System')
        added_uid = session.get('user_id', 0)
        
        for user_id in user_ids:
            doc_ref = db.collection('notifications').document()  # auto-ID
            doc_ref.set({
                'uid': int(user_id),
                'title': title,
                'content': content,
                'added_by': added_by,
                'added_uid': int(added_uid),
                'added_date': datetime.now(),
                'triggered': False,
                'read': False,
            })
        
        return len(user_ids)  # Return number of notifications sent
    except Exception as e:
        print(f"Error sending notifications to role {role_name}: {e}")
        return 0
def calculate_duration_days(start_date, end_date):
    """Calculate duration in days between two dates (inclusive)"""
    if not start_date:
        return 0
    
    # Convert string dates to date objects if needed
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str) and end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    elif not end_date:
        end_date = start_date
    
    # Ensure end date is not before start date
    if end_date < start_date:
        return 0
    
    # Calculate inclusive days (+1 to include both start and end)
    return (end_date - start_date).days + 1

def log_request_change(request_id, action_type, action_by, field_name=None, old_value=None, new_value=None, change_description=None, conn=None, cur=None):
    """
    Log changes to sales requests in the change log table
    
    Parameters:
    - request_id: The ID of the request being changed
    - action_type: Type of action (CREATE, UPDATE, DELETE, STATUS_CHANGE, COST_UPDATE, etc.)
    - action_by: Username of the person making the change
    - field_name: Name of the field being changed (optional for CREATE/DELETE)
    - old_value: Previous value of the field (optional)
    - new_value: New value of the field (optional)
    - change_description: Human-readable description of the change (optional)
    - conn: Existing database connection (optional, creates new if not provided)
    - cur: Existing database cursor (optional, creates new if not provided)
    """
    # OPTIMIZATION: Use existing connection if provided to prevent lock contention
    own_connection = False
    try:
        if conn is None or cur is None:
            conn, cur = connection()
            own_connection = True
        
        # Get IP address from request context
        ip_address = None
        try:
            if request and hasattr(request, 'remote_addr'):
                ip_address = request.remote_addr
        except:
            pass
        
        # Convert complex values to JSON strings for storage
        if old_value and not isinstance(old_value, str):
            old_value = json.dumps(old_value) if isinstance(old_value, (dict, list)) else str(old_value)
        if new_value and not isinstance(new_value, str):
            new_value = json.dumps(new_value) if isinstance(new_value, (dict, list)) else str(new_value)
        
        # Insert log entry
        cur.execute("""
            INSERT INTO sales_request_change_log 
            (request_id, action_type, action_by, field_name, old_value, new_value, change_description, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            request_id,
            action_type,
            action_by,
            field_name,
            old_value,
            new_value,
            change_description,
            ip_address
        ))
        
        # Only commit and close if we created our own connection
        if own_connection:
            conn.commit()
            cur.close()
            conn.close()
        
    except Exception as e:
        print(f"Error logging request change: {str(e)}")
        traceback.print_exc()

def log_item_change(request_id, item_id, item_name, request_type, action_type, action_by, old_data=None, new_data=None, change_description=None, conn=None, cur=None):
    """
    Log changes to items within a sales request using the main sales_request_change_log table
    
    Parameters:
    - request_id: The ID of the sales request
    - item_id: The ID of the item
    - item_name: Name of the item
    - request_type: Request type the item belongs to (Event, Production, etc.)
    - action_type: Type of action (ITEM_ADD, ITEM_UPDATE, ITEM_DELETE, ATTACHMENT_ADD, ATTACHMENT_REMOVE)
    - action_by: Username of the person making the change
    - old_data: Dict of old item data (for updates)
    - new_data: Dict of new item data (for adds/updates)
    - change_description: Human-readable description (auto-generated if not provided)
    - conn: Existing database connection (optional, creates new if not provided)
    - cur: Existing database cursor (optional, creates new if not provided)
    """
    try:
        # Detect individual field changes for granular logging
        field_changes = []
        if action_type == 'ITEM_UPDATE' and old_data and new_data:
            # Check all possible item fields for changes
            for field in ['name', 'qty', 'quantity', 'unit', 'description', 'comment', 'width', 'height', 'depth', 'cost_per_item', 'sell_per_item', 'total_cost', 'total_sell']:
                old_val = old_data.get(field)
                new_val = new_data.get(field)
                
                # Skip if both are None or empty
                if not old_val and not new_val:
                    continue
                    
                # Convert to string for comparison
                old_str = str(old_val) if old_val is not None else ''
                new_str = str(new_val) if new_val is not None else ''
                
                if old_str != new_str:
                    field_changes.append({
                        'field': field,
                        'old': old_val,
                        'new': new_val
                    })
        
        # If we have specific field changes, log each one separately
        if field_changes:
            for change in field_changes:
                # Format field-specific description
                field_display = change['field'].replace('_', ' ').title()
                if request_type:
                    full_desc = f"[{request_type}] Item '{item_name}': {field_display} changed from '{change['old']}' to '{change['new']}'"
                else:
                    full_desc = f"Item '{item_name}': {field_display} changed from '{change['old']}' to '{change['new']}'"
                
                # Use the main logging function WITH SAME CONNECTION
                log_request_change(
                    request_id=request_id,
                    action_type='ITEM_UPDATE',
                    action_by=action_by,
                    field_name=f"item_{item_id}_{change['field']}",
                    old_value=str(change['old']) if change['old'] is not None else None,
                    new_value=str(change['new']) if change['new'] is not None else None,
                    change_description=full_desc,
                    conn=conn,
                    cur=cur
                )
        else:
            # No specific field changes or non-UPDATE action, log as single entry
            # Auto-generate description if not provided
            if not change_description:
                if action_type == 'ITEM_ADD':
                    qty_info = f" (Qty: {new_data.get('qty', new_data.get('quantity', 'N/A'))} {new_data.get('unit', 'pcs')})" if new_data else ""
                    if request_type:
                        change_description = f"[{request_type}] Added item '{item_name}'{qty_info}"
                    else:
                        change_description = f"Added item '{item_name}'{qty_info}"
                elif action_type == 'ITEM_DELETE':
                    qty_info = f" (Qty: {old_data.get('qty', old_data.get('quantity', 'N/A'))} {old_data.get('unit', 'pcs')})" if old_data else ""
                    if request_type:
                        change_description = f"[{request_type}] Deleted item '{item_name}'{qty_info}"
                    else:
                        change_description = f"Deleted item '{item_name}'{qty_info}"
                elif action_type == 'ATTACHMENT_ADD':
                    attach_info = f" ({new_data.get('filename', 'file')})" if new_data and new_data.get('filename') else ""
                    if request_type:
                        change_description = f"[{request_type}] Added attachment{attach_info} to item '{item_name}'"
                    else:
                        change_description = f"Added attachment{attach_info} to item '{item_name}'"
                elif action_type == 'ATTACHMENT_REMOVE':
                    attach_info = f" ({old_data.get('filename', 'file')})" if old_data and old_data.get('filename') else ""
                    if request_type:
                        change_description = f"[{request_type}] Removed attachment{attach_info} from item '{item_name}'"
                    else:
                        change_description = f"Removed attachment{attach_info} from item '{item_name}'"
                else:
                    if request_type:
                        change_description = f"[{request_type}] {action_type} for item '{item_name}'"
                    else:
                        change_description = f"{action_type} for item '{item_name}'"
            
            # Convert data to JSON strings for old/new values
            old_value = json.dumps(old_data) if old_data and len(json.dumps(old_data)) < 1000 else None
            new_value = json.dumps(new_data) if new_data and len(json.dumps(new_data)) < 1000 else None
            
            # Use the main logging function WITH SAME CONNECTION
            log_request_change(
                request_id=request_id,
                action_type=action_type,
                action_by=action_by,
                field_name=f"item_{item_id}",
                old_value=old_value,
                new_value=new_value,
                change_description=change_description,
                conn=conn,
                cur=cur
            )
        
        print(f"DEBUG: Logged item change for request {request_id}, item {item_id} ({item_name}): {action_type}")
        
    except Exception as e:
        print(f"ERROR: Failed to log item change: {str(e)}")
        traceback.print_exc()
        # Don't fail the main operation if logging fails

PASSWORD_HASH_PREFIXES = ('scrypt:', 'pbkdf2:', 'argon2')


def verify_password(user, password, conn, cur):
    """
    Check a submitted password against the stored value.
    Rows still holding a legacy plaintext password are upgraded to a hash
    on the first successful login, so no flag day is needed.
    """
    stored = user.get('password') or ''
    if stored.startswith(PASSWORD_HASH_PREFIXES):
        return check_password_hash(stored, password)
    if not password or stored != password:
        return False
    cur.execute(
        "UPDATE user SET password = %s WHERE id = %s",
        (generate_password_hash(password), user['id'])
    )
    conn.commit()
    return True


@app.route('/login', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == "POST" and "add_login" in request.args:
        mobile     = request.form.get("mobile")      # we treat username as phone
        password  = request.form.get("password")
        # — 1) Verify your own MySQL user/password —
        # mobile is UNIQUE on user, so this returns at most one row.
        conn, cur = connection()
        exist=cur.execute("SELECT * FROM user WHERE mobile = %s", (mobile,))
        user = cur.fetchone() if int(exist) == 1 else None
        if user is None or not verify_password(user, password, conn, cur):
            cur.close()
            conn.close()
            return jsonify(
                state   = "error",
                message = "Invalid username or password"
            )
        cur.close()
        conn.close()
        # user is now a dict, use column names
        session['user_id'] = user['id']
        session['mobile'] = user['mobile']
        session['email'] = user['email']
        session['username'] = user['username']
        session['name'] = user['name']
        session['team_id'] = user['team_id']
        session['title'] = user['title']
        # Use the new function to get roles
        session['roles'] = get_user_roles(user['id'])
        # RBAC: permission set and role code, refreshed by /api/refresh-roles.
        session['perms'], session['role_code'] = load_permissions(user['id'])
        # — 2) Ensure a Firebase Auth user exists for this phone number —
        fb_mobile = "+20" + str(mobile).lstrip('0')  # Ensure all leading zeros are stripped
        # Validate Egyptian phone number (E.164: +20XXXXXXXXXX)
        def is_valid_egyptian_phone(phone):
            return re.match(r'^\+201[0-9]{9}$', phone) is not None
        if not is_valid_egyptian_phone(fb_mobile):
            return jsonify(state="error", message="Invalid phone number format for Firebase"), 400
        try:
            fb_user = auth.get_user_by_phone_number(fb_mobile)
        except auth.UserNotFoundError:
            # Create a new Firebase user with this phone as UID
            fb_user = auth.create_user(
                uid         = fb_mobile,
                phone_number= fb_mobile
            )
        # — 4) Mint a Firebase Custom Token so the client can sign in —
        custom_token = auth.create_custom_token(fb_user.uid).decode("utf-8")
        session['fb_uid'] = fb_user.uid  # Store Firebase UID in session
        session['token'] = custom_token
        session['fb_mobile'] = fb_mobile  # Store Firebase token in session
        # — 3) Optionally, store the phone number in the Firebase user profile —
        # — 5) Return success, the custom token, and any redirect info —
        return jsonify(
            state          = "success",
            message        = "Login successful",
            firebase_token = custom_token,
            redirect       = url_for("home")    # or wherever
        )
    # GET → render the login page
    return render_template("login.html")





@app.route('/firebase-messaging-sw.js')
def firebase_messaging_sw():
    return send_from_directory('static', 'firebase-messaging-sw.js', mimetype='application/javascript')

@app.route('/add_notification', methods=['POST'])
def add_notification():
    if 'user_id' not in session:
        return jsonify(success=False, error="Not authenticated"), 401

    data    = request.get_json() or {}
    uid     = data.get('uid')
    title   = data.get('title')
    content = data.get('content')
    added_by = session.get('name')
    added_uid = session['user_id']

    if not title or not content:
        return jsonify(success=False, error="Missing title or content"), 400

    if uid in (None, ''):
        return jsonify(success=False, error="Missing uid"), 400
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return jsonify(success=False, error="Invalid uid"), 400

    doc_ref = db.collection('notifications').document()  # auto-ID
    doc_ref.set({
        'uid':         uid,
        'title':       title,
        'content':     content,
        'added_by':     added_by,
        'added_uid':     int(added_uid),
        'added_date':  datetime.datetime.utcnow(),
        'triggered':   False,
        'read':        False,
    })

    return jsonify(success=True, message_id=doc_ref.id)
@app.route('/get_notifications')
def get_notifications():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401

        # Get reference to Firestore
        
        
        # Query notifications for the current user
        notifications_ref = db.collection('notifications')
        print(session['user_id'])
        query = notifications_ref.where('uid', '==', session['user_id']).order_by('added_date', direction=firebase_admin.firestore.Query.DESCENDING).limit(50)
        
        # Get the documents
        docs = query.get()
        
        # Convert to list of dictionaries
        notifications = []
        for doc in docs:
            data = doc.to_dict()
            # Convert timestamp to string for JSON serialization
            if 'added_date' in data:
                # Handle both timestamp and string dates
                if hasattr(data['added_date'], 'timestamp'):
                    # It's a Firestore timestamp
                    data['timeadded_datestamp'] = data['added_date'].isoformat()
                else:
                    # It's already a string or datetime
                    try:
                        if isinstance(data['added_date'], str):
                            # Try to parse and reformat
                            parsed_date = datetime.strptime(data['added_date'], '%Y-%m-%d %H:%M:%S')
                            data['timeadded_datestamp'] = parsed_date.isoformat()
                        else:
                            data['timeadded_datestamp'] = data['added_date'].isoformat()
                    except:
                        data['timeadded_datestamp'] = str(data['added_date'])
            else:
                data['timeadded_datestamp'] = datetime.now().isoformat()
                
            notifications.append({
                'id': doc.id,
                **data
            })
        
        return jsonify({
            'success': True,
            'notifications': notifications
        })
    except Exception as e:
        print(f"Error fetching notifications: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/mark_notifications_read', methods=['POST'])
def mark_notifications_read():
    """Mark notifications as read"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401

        data = request.get_json()
        notification_ids = data.get('notification_ids', [])
        
        if not notification_ids:
            # Mark all notifications as read for the user
            notifications_ref = db.collection('notifications')
            query = notifications_ref.where('uid', '==', session['user_id']).where('read', '==', False)
            docs = query.get()
            
            for doc in docs:
                doc.reference.update({'read': True})
        else:
            # Mark specific notifications as read
            for notif_id in notification_ids:
                doc_ref = db.collection('notifications').document(notif_id)
                doc_ref.update({'read': True})
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error marking notifications as read: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/notifications')
def all_notifications():
    """Display all notifications page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template("notifications.html")

@app.route('/api/refresh-roles', methods=['POST'])
def refresh_user_roles():
    """API endpoint to refresh user roles in session"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        user_id = session['user_id']
        
        # Get fresh roles from database
        fresh_roles = get_user_roles(user_id)

        # Update session with fresh roles
        session['roles'] = fresh_roles

        # RBAC: refresh the permission set too, so a role change takes effect
        # on the next poll rather than at the next login.
        fresh_perms, role_code = load_permissions(user_id)
        session['perms'] = fresh_perms
        session['role_code'] = role_code

        return jsonify({
            'success': True,
            'roles': fresh_roles,
            'perms': fresh_perms,
            'role_code': role_code,
            'message': 'Roles refreshed successfully'
        })
        
    except Exception as e:
        print(f"Error refreshing roles: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route("/subscribe", methods=["POST"])
def subscribe():
    # 1) Ensure they're logged in
    user_id = session.get("user_id")
    if not user_id:
        return abort(401)

    # 2) Read the real FCM registration token from the request
    data      = request.get_json(silent=True) or {}
    reg_token = data.get("fcm_token")
    if not reg_token:
        return jsonify(error="Missing fcm_token"), 400
    session['fcm_token'] = reg_token
    # 3) Build a safe topic name
    topic = f"user_{user_id}"  # e.g. "user_42"

    # 4) Subscribe that registration token
    try:
        response = messaging.subscribe_to_topic([reg_token], topic)
    # abort(404) raises an HTTPException; letting the blanket handler below
    # catch it would report a missing file as a server error.
    except HTTPException:
        raise
    except Exception as e:
        current_app.logger.error("FCM subscribe failed: %s", e)
        return jsonify(error="Subscribe failed"), 500

    # 5) Check result
    if response.success_count == 1:
        return jsonify(success=True)
    else:
        errs = "; ".join(f"{err.index}:{err.reason}" for err in response.errors or [])
        current_app.logger.error("Subscription errors: %s", errs)
        return jsonify(error="Subscribe failed: "+errs), 400

@app.route('/main', methods=['GET','POST']) 
def main():

    return render_template("main.html")


@app.route("/home", methods=["GET", "POST"])
def home():
    # Ensure we have both a logged-in user and a valid reg-token
    user_id   = session.get("user_id")
    reg_token = session.get("fcm_token")
    
    # Debug: Print session information
    print("=== HOME PAGE DEBUG ===")
    print(f"User ID: {user_id}")
    print(f"Session keys: {list(session.keys())}")
    print(f"User roles: {session.get('roles', [])}")
    print(f"Username: {session.get('username')}")
    print("=====================")
    
    if not user_id:
        return redirect(url_for('login'))
    
    # Render your page
    return render_template("home.html")

@app.route('/logout', methods=['GET','POST']) 
def logout():
    session.clear()
    return redirect(url_for('login'))
    

def send_test_notification(reg_token: str, title: str, body: str) -> str:
    """
    Sends a notification to one device token.
    Returns the FCM message ID on success, or raises on failure.
    """
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        token=reg_token  # MUST be the registration token from getToken()
    )
    # This will raise firebase_admin.exceptions.FirebaseError on failure
    return messaging.send(message)









    
### AL MAL3AAAB ###
def get_access_token():
    """Generate access token using the Service Account JSON."""
    service_account_file = './eltime-6571b-firebase-adminsdk-71oq0-1b7a4414ce.json'
    
    # Load the service account credentials using google.auth
    creds, project = google.auth.load_credentials_from_file(service_account_file)
    
    # Define the required scope for FCM
    scopes = ['https://www.googleapis.com/auth/firebase.messaging']

    # If the credentials do not have the necessary scope, add it
    creds = creds.with_scopes(scopes)
    
    # Refresh the credentials to get the access token
    creds.refresh(Request())

    # Return the access token
    return creds.token
def push_send_notification(mobile,title,content):
                try:
                    initialize_firebase()
                    phone_numbers = []
                    
                    phone_numbers.append(f"0{str(mobile)}")  # Add more numbers as needed
            
                    # Get FCM tokens for users with the given phone numbers
                    
                    user_details = get_users_with_phone_numbers(phone_numbers)
                    print(user_details)
                    for phone_number in user_details.keys():
                        tokens = user_details[phone_number]['token']  # Access using key
                        uid = user_details[phone_number]['uid']      # Access using key
                        email = user_details[phone_number]['email']  # Access using key
                        

                        #insert_notification(uid, email, student_id, title, content)
                        if tokens:
                            for token in tokens:
                                        send_notification(token,title,content)
                        else:
                                print("No tokens found for the specified phone numbers.")
                    
                except Exception as e:
                        print(f"Unexpected error: {e}")

def get_users_with_phone_numbers(phone_numbers):
    db = firestore.client()
    users_ref = db.collection('user')

    # Query documents where 'phone_number' is in the list of phone numbers
    # Query users with the specified phone numbers and where 'student_id' is not null
    query = users_ref \
    .where("phone_number", "in", phone_numbers) \
    .stream()

    tokens = []
    user_all_info_dict={}
    
    for doc in query:
        user_data = doc.to_dict()
        print(f"Document ID: {doc.id}, Data: {user_data}")

        # If fcm_tokens is a subcollection, query it
        fcm_tokens_ref = db.collection('user').document(doc.id).collection('fcm_tokens').stream()
        
        # Retrieve fcmToken from the subcollection
        print(fcm_tokens_ref)
        for token_doc in fcm_tokens_ref:
            token_data = token_doc.to_dict()
            print(f"Token: {token_data}")
            if 'fcm_token' in token_data:
                tokens.append(token_data['fcm_token'])
        user_all_info_dict[user_data['phone_number']]={"uid":user_data['uid'],"email":user_data['email'],"token":tokens}

    return user_all_info_dict
def send_notification(device_token,msg_title,msg_body):
    """Send a notification to the specified FCM device token."""
    try:
        fcm_url = "https://fcm.googleapis.com/v1/projects/eltime-6571b/messages:send"

        # Get the access token using Service Account JSON file
        server_key = get_access_token()  # Get the access token from the service account

        if not server_key:
            print("Error: Server key is missing. Please set a valid Firebase server key.")
            return

        message = {
            "message": {
                "token": device_token,
                "notification": {
                    "title": f"{msg_title}",
                    "body": f"{msg_body}",
                }
            }
        }

        headers = {
            'Authorization': f'Bearer {server_key}',
            'Content-Type': 'application/json; UTF-8',
        }

        response = requests.post(fcm_url, headers=headers, data=json.dumps(message))

        if response.status_code == 200:
            print(f"Notification sent successfully to token: {device_token}")
        else:
            print(f"Error sending notification to {device_token}: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error sending notification: {e}")

@app.route('/users', methods=['GET'])
@perm('user.view')
def users():
    """Display users page with user data table"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template("users.html")

@app.route('/api/users', methods=['GET'])
@perm('user.view')
def get_users():
    """API endpoint to fetch users data from MySQL"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401

    try:
        conn, cur = connection()

        # Passwords are never returned to the client.
        cur.execute("""
            SELECT u.id, u.mobile, u.email, u.date, u.name, u.modified_date, u.added_by, u.username, u.title,
                   u.department_id, u.rbac_role_id, u.manager_id, u.is_pricing,
                   d.name AS rbac_department_name, d.code AS rbac_department_code,
                   r.code AS role_code, r.name AS role_name, r.level AS role_level,
                   m.name AS manager_name
            FROM user u
            LEFT JOIN department d ON d.id = u.department_id
            LEFT JOIN rbac_role r ON r.id = u.rbac_role_id
            LEFT JOIN user m ON m.id = u.manager_id
            ORDER BY u.id DESC
        """)
        users_data = cur.fetchall()
        # Convert to list of dictionaries for JSON response
        users_list = []
        for user in users_data:
            users_list.append({
                'id': user['id'],
                'mobile': user['mobile'],
                'email': user['email'],
                'name': user['name'],
                'date': user['date'].strftime('%Y-%m-%d %H:%M:%S') if user['date'] else 'N/A',
                'modified_date': user['modified_date'].strftime('%Y-%m-%d %H:%M:%S') if user['modified_date'] else 'N/A',
                'added_by': user['added_by'],
                'username': user['username'],
                'title': user['title'],
                # RBAC hierarchy
                'department_id': user['department_id'],
                'rbac_department_name': user['rbac_department_name'],
                'rbac_department_code': user['rbac_department_code'],
                'rbac_role_id': user['rbac_role_id'],
                'role_code': user['role_code'],
                'role_name': user['role_name'],
                'role_level': user['role_level'],
                'manager_id': user['manager_id'],
                'manager_name': user['manager_name'],
                'is_pricing': bool(user['is_pricing'])
            })
        cur.close()
        conn.close()
        return jsonify({
            'success': True,
            'users': users_list
        })
    except Exception as e:
        print(e)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/users/add', methods=['POST'])
@perm('user.create')
def add_user():
    """API endpoint to add a new user"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'mobile', 'email', 'password', 'username', 'title']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        print(data.get('team_id'))
        conn, cur = connection()
        
        # Check if mobile already exists
        cur.execute("SELECT id FROM user WHERE mobile = %s", (data['mobile'],))
        if cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'Mobile number already exists'
            }), 400
            
        # Check if email already exists
        cur.execute("SELECT id FROM user WHERE email = %s", (data['email'],))
        if cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'Email already exists'
            }), 400
        
        # Check if username already exists
        cur.execute("SELECT id FROM user WHERE username = %s", (data['username'],))
        if cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'Username already exists'
            }), 400
        
        # Convert team_id to int or None
        team_id = data.get('team_id')
        if team_id in [None, '', 'undefined']:
            team_id = None
        else:
            try:
                team_id = int(team_id)
            except Exception:
                team_id = None
        
        # RBAC hierarchy: department, role and reporting line.
        hierarchy, hierarchy_error = _hierarchy_fields(data)
        if hierarchy_error:
            return jsonify({'success': False, 'error': hierarchy_error}), 400
        validation_error = _validate_hierarchy(cur, hierarchy)
        if validation_error:
            return jsonify({'success': False, 'error': validation_error}), 400

        # Insert new user with username, title, and team_id
        cur.execute("""
            INSERT INTO user (name, mobile, email, password, username, title, team_id, date, added_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s)
        """, (
            data['name'],
            data['mobile'],
            data['email'],
            generate_password_hash(data['password']),
            data['username'],
            data['title'],
            team_id,
            session['username']
        ))
        
        conn.commit()
        
        # Get the new user's ID
        new_user_id = cur.lastrowid

        if hierarchy:
            assignments = ", ".join("%s = %%s" % key for key in hierarchy)
            cur.execute(
                "UPDATE user SET %s WHERE id = %%s" % assignments,
                list(hierarchy.values()) + [new_user_id]
            )
            conn.commit()

        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'User added successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/users/delete/<int:user_id>', methods=['DELETE'])
@perm('user.delete')
def delete_user(user_id):
    """API endpoint to delete a user"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Check if user exists
        cur.execute("SELECT id FROM user WHERE id = %s", (user_id,))
        if not cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404

        # Nobody may delete their own account, and user 1 is the recovery account.
        if user_id == session.get('user_id') or user_id == 1:
            return jsonify({
                'success': False,
                'error': 'This account cannot be deleted'
            }), 400

        # Delete user
        cur.execute("DELETE FROM user WHERE id = %s", (user_id,))
        conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'User deleted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/users/edit/<int:user_id>', methods=['POST'])
@perm('user.edit')
def edit_user(user_id):
    """API endpoint to edit an existing user"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401

    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['name', 'mobile', 'email', 'username', 'title']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400

        conn, cur = connection()

        # Check for duplicate mobile number
        cur.execute("SELECT id FROM user WHERE mobile = %s AND id != %s", (data['mobile'], user_id))
        if cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'Mobile number already exists'
            }), 400

        # Check for duplicate email
        cur.execute("SELECT id FROM user WHERE email = %s AND id != %s", (data['email'], user_id))
        if cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'Email already exists'
            }), 400

        # Check for duplicate username
        cur.execute("SELECT id FROM user WHERE username = %s AND id != %s", (data['username'], user_id))
        if cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'Username already exists'
            }), 400

        # Update user details
        cur.execute("""
            UPDATE user
            SET name = %s, mobile = %s, email = %s, username = %s, title = %s,
                modified_date = NOW(), modified_by = %s
            WHERE id = %s
        """, (
            data['name'],
            data['mobile'],
            data['email'],
            data['username'],
            data['title'],
            session['username'],
            user_id
        ))

        # RBAC hierarchy, same rule: only keys the client actually sent are applied.
        hierarchy, hierarchy_error = _hierarchy_fields(data)
        if hierarchy_error:
            return jsonify({'success': False, 'error': hierarchy_error}), 400
        validation_error = _validate_hierarchy(cur, hierarchy, user_id=user_id)
        if validation_error:
            return jsonify({'success': False, 'error': validation_error}), 400
        if hierarchy:
            assignments = ", ".join("%s = %%s" % key for key in hierarchy)
            cur.execute(
                "UPDATE user SET %s WHERE id = %%s" % assignments,
                list(hierarchy.values()) + [user_id]
            )

        # team_id is only touched when the client actually sends the key, so an
        # edit form that omits it does not silently unassign the user's team.
        if 'team_id' in data:
            team_id = data.get('team_id')
            if team_id in [None, '', 'undefined']:
                team_id = None
            else:
                try:
                    team_id = int(team_id)
                except Exception:
                    team_id = None
            cur.execute("UPDATE user SET team_id = %s WHERE id = %s", (team_id, user_id))

        # The password field is optional on edit; an empty value leaves it unchanged.
        new_password = (data.get('password') or '').strip()
        if new_password:
            cur.execute(
                "UPDATE user SET password = %s WHERE id = %s",
                (generate_password_hash(new_password), user_id)
            )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'User updated successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ---------------------------------------------------------------------------
# Departments, roles and the reporting line
# ---------------------------------------------------------------------------

@app.route('/api/departments', methods=['GET'])
@perm('department.view')
def get_departments():
    """List departments with how many teams and users sit in each."""
    try:
        conn, cur = connection()
        cur.execute("""
            SELECT d.id, d.code, d.name,
                   (SELECT COUNT(*) FROM team t WHERE t.department_id = d.id) AS team_count,
                   (SELECT COUNT(*) FROM user u WHERE u.department_id = d.id) AS user_count
            FROM department d
            ORDER BY d.name
        """)
        departments = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(success=True, departments=departments)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route('/api/departments', methods=['POST'])
@perm('department.edit')
def add_department():
    """Create a department. `code` is the stable key, `name` is the label."""
    try:
        data = request.get_json() or {}
        code = (data.get('code') or '').strip().lower().replace(' ', '_')
        name = (data.get('name') or '').strip()
        if not code or not name:
            return jsonify(success=False, error='Both code and name are required'), 400

        conn, cur = connection()
        cur.execute("SELECT id FROM department WHERE code = %s", (code,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify(success=False, error='A department with that code already exists'), 400

        cur.execute("INSERT INTO department (code, name) VALUES (%s, %s)", (code, name))
        conn.commit()
        new_id = cur.lastrowid
        cur.close()
        conn.close()
        return jsonify(success=True, id=new_id, message='Department created')
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route('/api/departments/<int:department_id>', methods=['PUT'])
@perm('department.edit')
def edit_department(department_id):
    """
    Rename a department. The code is deliberately immutable: rbac.py and the
    seed refer to departments by code, so changing it would orphan the roles.
    """
    try:
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify(success=False, error='Name is required'), 400

        conn, cur = connection()
        cur.execute("UPDATE department SET name = %s WHERE id = %s", (name, department_id))
        conn.commit()
        updated = cur.rowcount
        cur.close()
        conn.close()
        if not updated:
            return jsonify(success=False, error='Department not found'), 404
        return jsonify(success=True, message='Department renamed')
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route('/api/rbac/roles', methods=['GET'])
@perm('role.view')
def get_rbac_roles():
    """List roles with their department and how many permissions each holds."""
    try:
        conn, cur = connection()
        cur.execute("""
            SELECT r.id, r.code, r.name, r.level, r.department_id,
                   d.code AS department_code, d.name AS department_name,
                   (SELECT COUNT(*) FROM role_permission rp WHERE rp.role_id = r.id) AS permission_count
            FROM rbac_role r
            LEFT JOIN department d ON d.id = r.department_id
            ORDER BY d.name, r.level, r.name
        """)
        roles = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(success=True, roles=roles)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route('/api/rbac/roles/<int:role_id>/permissions', methods=['GET'])
@perm('role.view')
def get_rbac_role_permissions(role_id):
    """
    Show what a role can do. Read-only: the grant matrix lives in rbac.py and
    is applied by seed_rbac.py, so it is reviewed in code rather than edited here.
    """
    try:
        conn, cur = connection()
        cur.execute("SELECT id, code, name, level FROM rbac_role WHERE id = %s", (role_id,))
        role = cur.fetchone()
        if not role:
            cur.close()
            conn.close()
            return jsonify(success=False, error='Role not found'), 404

        cur.execute("""
            SELECT rp.permission_code, rp.scope, p.description
            FROM role_permission rp
            JOIN permission p ON p.code = rp.permission_code
            WHERE rp.role_id = %s
            ORDER BY rp.permission_code
        """, (role_id,))
        permissions = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(success=True, role=role, permissions=permissions)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route('/api/rbac/managers', methods=['GET'])
@perm('user.view')
def get_manager_candidates():
    """
    Candidate managers for a role: anyone holding a role at a higher level
    (numerically lower). Passing no role_id returns everyone with a role.
    """
    try:
        role_id = request.args.get('role_id')
        exclude_user_id = request.args.get('exclude_user_id')

        conn, cur = connection()
        sql = """
            SELECT u.id, u.name, u.username, r.name AS role_name, r.level,
                   d.name AS department_name
            FROM user u
            JOIN rbac_role r ON r.id = u.rbac_role_id
            LEFT JOIN department d ON d.id = u.department_id
            WHERE 1=1
        """
        params = []
        if role_id:
            cur.execute("SELECT level FROM rbac_role WHERE id = %s", (role_id,))
            row = cur.fetchone()
            if row:
                sql += " AND r.level < %s"
                params.append(row['level'])
        if exclude_user_id:
            sql += " AND u.id != %s"
            params.append(exclude_user_id)
        sql += " ORDER BY r.level, u.name"

        cur.execute(sql, params)
        managers = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(success=True, managers=managers)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


def _hierarchy_fields(data):
    """
    Pull department_id / rbac_role_id / manager_id off a request payload.
    Returns (fields, error). Only keys actually present are returned, so a
    form that omits them leaves the stored values alone.
    """
    fields = {}
    # Pricing is a flag rather than a role, so it rides along with the other
    # position fields and follows the same only-if-sent rule.
    if 'is_pricing' in data:
        fields['is_pricing'] = 1 if data.get('is_pricing') in (True, 1, '1', 'true', 'on') else 0
    for key in ('department_id', 'rbac_role_id', 'manager_id'):
        if key not in data:
            continue
        value = data.get(key)
        if value in (None, '', 'undefined', 'null'):
            fields[key] = None
            continue
        try:
            fields[key] = int(value)
        except (TypeError, ValueError):
            return None, 'Invalid %s' % key
    return fields, None


def _validate_hierarchy(cur, fields, user_id=None):
    """Reject a role/department mismatch, a missing manager, or a reporting cycle."""
    role_id = fields.get('rbac_role_id')
    manager_id = fields.get('manager_id')

    if role_id:
        cur.execute("SELECT id, level, department_id FROM rbac_role WHERE id = %s", (role_id,))
        if not cur.fetchone():
            return 'Unknown role'

    if manager_id:
        if manager_id == user_id:
            return 'A user cannot report to themselves'
        cur.execute("""
            SELECT r.level FROM user u
            LEFT JOIN rbac_role r ON r.id = u.rbac_role_id
            WHERE u.id = %s
        """, (manager_id,))
        manager = cur.fetchone()
        if not manager:
            return 'Unknown manager'
        if role_id and manager['level'] is not None:
            cur.execute("SELECT level FROM rbac_role WHERE id = %s", (role_id,))
            own_level = cur.fetchone()['level']
            if manager['level'] >= own_level:
                return 'A manager must hold a more senior role than their report'

        # Walk the reporting line upward; a cycle would make team scope loop.
        if user_id:
            seen = {user_id}
            cursor_id = manager_id
            for _ in range(20):
                if cursor_id in seen:
                    return 'That manager would create a reporting cycle'
                seen.add(cursor_id)
                cur.execute("SELECT manager_id FROM user WHERE id = %s", (cursor_id,))
                row = cur.fetchone()
                cursor_id = row['manager_id'] if row else None
                if not cursor_id:
                    break
    return None


# Endpoints that legitimately carry no permission gate. Everything here except
# login and static still sits behind the session check below. Kept next to
# require_login so the two are read together; tests/test_route_coverage.py
# asserts every other route is gated.
PUBLIC_ENDPOINTS = {
    'static',
    'login', 'logout', 'main', 'home',
    'subscribe', 'firebase_messaging_sw', 'refresh_user_roles',
    'get_notifications', 'mark_notifications_read', 'all_notifications',
    'add_notification',
    'serve_item_attachment', 'sales_requests_lookup',
}


@app.before_request
def require_login():
    """
    Enforce session-based authentication for all endpoints except login and public endpoints.
    Redirects to login if required session variables are missing.
    """
    # List of endpoints that do NOT require login
    allowed_routes = [
        'login', 'static', 'firebase_messaging_sw'
    ]
    
    # Allow static files, favicon, etc.
    if request.endpoint in allowed_routes or request.endpoint is None:
        return
    
    # Allow GET to root (/) for login page
    if request.path in ['/', '/login']:
        return
    
    # Check if all required session variables are present
    required_session_vars = ['user_id', 'mobile', 'email', 'username', 'name']
    
    for var in required_session_vars:
        if var not in session:
            # For API requests, return JSON error
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Not authenticated'}), 401
            # For normal requests, redirect to login
            return redirect(url_for('login'))

    # Default deny. A route that carries no permission gate and is not on the
    # public list is refused outright, so a handler added without a decorator
    # fails closed in development instead of shipping open.
    view = app.view_functions.get(request.endpoint)
    if view is not None and request.endpoint not in PUBLIC_ENDPOINTS \
            and not getattr(view, '_perms', None):
        app.logger.warning('Ungated endpoint refused: %s (%s)', request.endpoint, request.path)
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Forbidden'}), 403
        return abort(403)


@app.route('/management_admin', methods=['GET'])
@perm('user.view', 'client.edit', 'company.edit', 'supplier.edit', 'entity.edit')
def management_admin():
    """Display admin section landing page with dashboard and sub-page links"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template("admin_section.html")

@app.route('/sales_mainpage', methods=['GET'])
@perm('sales_request.view')
def sales_mainpage():
    """Display sales section landing page with dashboard and sub-page links"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template("sales_mainpage.html")

@app.route('/operation_mainpage', methods=['GET'])
@perm('approved_item.view')
def operation_mainpage():
    """Display operations section landing page with dashboard and sub-page links"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template("operation_mainpage.html")

@app.route('/approved-items', methods=['GET'])
@perm('approved_item.view')
def approved_items_page():
    """Display client approved items page"""
    return render_template("approved_items.html")

@app.route('/api/operations/approved-items', methods=['GET'])
@perm('approved_item.view')
def get_approved_items():
    """Get all client-approved items with sales request details"""
    try:
        client_id = request.args.get('client_id')
        date_range = request.args.get('date_range', 'all')
        sell_type = request.args.get('sell_type')
        
        conn, cur = connection()
        
        # Build query for approved items
        query = """
            SELECT 
                sri.id,
                sri.request_id,
                sri.name,
                sri.description,
                sri.request_type,
                sri.qty,
                sri.unit,
                sri.sell_type,
                sri.rental_days,
                sri.cost_per_item,
                sri.sell_per_item,
                sri.total_cost,
                sri.total_sell,
                sri.approval_status,
                sri.client_approval_date,
                sri.client_feedback,
                sri.attributes,
                sri.supplier_id,
                sri.has_components,
                sup.supplier_name as item_supplier_name,
                sr.title as request_title,
                sr.client_id,
                sr.start_date,
                sr.end_date,
                sr.priority,
                sr.status as request_status,
                c.client_name
            FROM sales_request_items sri
            INNER JOIN sales_request sr ON sri.request_id = sr.id
            LEFT JOIN client c ON sr.client_id = c.id
            LEFT JOIN supplier sup ON sri.supplier_id = sup.id
            WHERE sri.approval_status = 'approved'
        """
        
        params = []
        
        # Apply filters
        if client_id:
            query += " AND sr.client_id = %s"
            params.append(client_id)
        
        if sell_type:
            query += " AND sri.sell_type = %s"
            params.append(sell_type)
        
        if date_range == 'today':
            query += " AND DATE(sri.client_approval_date) = CURDATE()"
        elif date_range == 'week':
            query += " AND sri.client_approval_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        elif date_range == 'month':
            query += " AND sri.client_approval_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
        
        query += " ORDER BY sri.client_approval_date DESC"
        
        cur.execute(query, params)
        items = cur.fetchall()
        
        # Process items
        items_list = []
        total_cost = 0
        total_sell = 0
        request_ids = set()
        
        for item in items:
            # Extract dimensions from attributes if available
            width = height = depth = None
            if item.get('attributes'):
                try:
                    attrs = item['attributes'] if isinstance(item['attributes'], dict) else json.loads(item['attributes'])
                    width = attrs.get('width')
                    height = attrs.get('height')
                    depth = attrs.get('depth')
                except:
                    pass
            
            item_data = {
                'id': item['id'],
                'request_id': item['request_id'],
                'name': item['name'],
                'description': item['description'],
                'request_type': item['request_type'],
                'qty': float(item['qty']) if item['qty'] else 1,
                'unit': item['unit'] or 'pcs',
                'sell_type': item['sell_type'] or 'rent',
                'rental_days': item['rental_days'] or 1,
                'cost_per_item': float(item['cost_per_item']) if item['cost_per_item'] else 0,
                'sell_per_item': float(item['sell_per_item']) if item['sell_per_item'] else 0,
                'total_cost': float(item['total_cost']) if item['total_cost'] else 0,
                'total_sell': float(item['total_sell']) if item['total_sell'] else 0,
                'client_approval_date': item['client_approval_date'].isoformat() if item['client_approval_date'] else None,
                'client_feedback': item['client_feedback'],
                'request_title': item['request_title'],
                'client_name': item['client_name'],
                'start_date': item['start_date'].isoformat() if item['start_date'] else None,
                'end_date': item['end_date'].isoformat() if item['end_date'] else None,
                'priority': item['priority'],
                'width': width,
                'height': height,
                'depth': depth,
                'supplier_id': item['supplier_id'],
                'supplier_name': item['item_supplier_name'],
                'has_components': bool(item['has_components'])
            }
            
            items_list.append(item_data)
            total_cost += item_data['total_cost']
            total_sell += item_data['total_sell']
            request_ids.add(item['request_id'])
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'items': items_list,
            'stats': {
                'total_items': len(items_list),
                'total_requests': len(request_ids),
                'total_cost': total_cost,
                'total_sell': total_sell
            }
        })
        
    except Exception as e:
        print(f"Error fetching approved items: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ===================== APPROVED ITEMS EXCEL EXPORTS =====================

def _approved_items_fetch_all():
    """Internal helper: fetch all approved items joined with request + supplier info for exports."""
    conn, cur = connection()
    cur.execute("""
        SELECT
            sri.id, sri.request_id, sri.name, sri.description, sri.request_type,
            sri.qty, sri.unit, sri.sell_type, sri.rental_days,
            sri.cost_per_item, sri.sell_per_item, sri.total_cost, sri.total_sell,
            sri.approval_status, sri.client_approval_date, sri.client_feedback,
            sri.attributes, sri.has_components,
            sri.supplier_id, sup.supplier_name, sup.primary_phone AS supplier_phone,
            sup.email_address AS supplier_email,
            sr.title AS request_title, sr.start_date, sr.end_date, sr.priority,
            sr.status AS request_status,
            c.client_name
        FROM sales_request_items sri
        INNER JOIN sales_request sr ON sri.request_id = sr.id
        LEFT JOIN client c ON sr.client_id = c.id
        LEFT JOIN supplier sup ON sri.supplier_id = sup.id
        WHERE sri.approval_status = 'approved'
        ORDER BY sri.request_id DESC, sri.id
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def _approved_item_row_to_dict(item):
    width = height = depth = None
    if item.get('attributes'):
        try:
            attrs = item['attributes'] if isinstance(item['attributes'], dict) else json.loads(item['attributes'])
            width = attrs.get('width')
            height = attrs.get('height')
            depth = attrs.get('depth')
        except Exception:
            pass
    return {
        'Item ID': item['id'],
        'Request ID': item['request_id'],
        'Request Title': item.get('request_title') or '',
        'Client': item.get('client_name') or '',
        'Item Name': item.get('name') or '',
        'Description': item.get('description') or '',
        'Type': item.get('sell_type') or '',
        'Quantity': float(item['qty']) if item.get('qty') else 0,
        'Unit': item.get('unit') or 'pcs',
        'Rental Days': item.get('rental_days') or 1,
        'Width': width, 'Height': height, 'Depth': depth,
        'Cost/Unit': float(item['cost_per_item']) if item.get('cost_per_item') else 0,
        'Total Cost': float(item['total_cost']) if item.get('total_cost') else 0,
        'Supplier': item.get('supplier_name') or 'Unassigned',
        'Supplier Phone': item.get('supplier_phone') or '',
        'Supplier Email': item.get('supplier_email') or '',
        'Request Start': item['start_date'].isoformat() if item.get('start_date') else '',
        'Request End': item['end_date'].isoformat() if item.get('end_date') else '',
        'Approval Date': item['client_approval_date'].isoformat() if item.get('client_approval_date') else '',
    }


def _safe_sheet_name(name, max_len=31):
    if name is None:
        name = 'Sheet'
    s = str(name)
    for ch in ['\\', '/', '*', '[', ']', ':', '?']:
        s = s.replace(ch, '_')
    s = s.strip()
    if not s:
        s = 'Sheet'
    return s[:max_len]


def _autosize_worksheet(ws, min_width=8, max_width=80, padding=2):
    """Auto-fit each column width to the longest cell text in the worksheet."""
    try:
        from openpyxl.utils import get_column_letter
        for col_idx, col_cells in enumerate(ws.columns, start=1):
            max_len = 0
            for cell in col_cells:
                val = cell.value
                if val is None:
                    continue
                # Consider widest line for multi-line text
                text = str(val)
                line_len = max((len(line) for line in text.splitlines()), default=len(text))
                if line_len > max_len:
                    max_len = line_len
            width = max(min_width, min(max_width, max_len + padding))
            ws.column_dimensions[get_column_letter(col_idx)].width = width
    except Exception as e:
        print(f"DEBUG: _autosize_worksheet error: {e}")


@app.route('/api/operations/approved-items/export/by-request', methods=['GET'])
@perm('approved_item.view')
def export_approved_by_request():
    """Excel workbook with one sheet per Approved Request listing its items."""
    try:
        rows = _approved_items_fetch_all()
        if not rows:
            return jsonify(success=False, error='No approved items found'), 404

        groups = {}
        for r in rows:
            rid = r['request_id']
            if rid not in groups:
                groups[rid] = {'title': r.get('request_title') or '', 'items': []}
            groups[rid]['items'].append(_approved_item_row_to_dict(r))

        buffer = BytesIO()
        used_names = set()
        with ExcelWriter(buffer, engine='openpyxl') as writer:
            for rid in sorted(groups.keys(), reverse=True):
                g = groups[rid]
                base = f"Req {rid} - {g['title']}" if g['title'] else f"Request {rid}"
                name = _safe_sheet_name(base)
                # Ensure unique sheet name
                final = name
                idx = 1
                while final in used_names:
                    suffix = f" ({idx})"
                    final = _safe_sheet_name(name[:31 - len(suffix)] + suffix)
                    idx += 1
                used_names.add(final)
                df = pd.DataFrame(g['items'])
                df.to_excel(writer, sheet_name=final, index=False)
                _autosize_worksheet(writer.sheets[final])

        buffer.seek(0)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(
            buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'approved_items_by_request_{ts}.xlsx'
        )
    except Exception as e:
        print(f"DEBUG: export_approved_by_request error: {e}")
        traceback.print_exc()
        return jsonify(success=False, error=str(e)), 500


@app.route('/api/operations/approved-items/export/by-supplier', methods=['GET'])
@perm('approved_item.view')
def export_approved_by_supplier():
    """Excel workbook with one sheet per Supplier listing the approved items assigned to them."""
    try:
        rows = _approved_items_fetch_all()
        if not rows:
            return jsonify(success=False, error='No approved items found'), 404

        groups = {}
        for r in rows:
            sname = r.get('supplier_name') or 'Unassigned'
            if sname not in groups:
                groups[sname] = []
            groups[sname].append(_approved_item_row_to_dict(r))

        buffer = BytesIO()
        used_names = set()
        with ExcelWriter(buffer, engine='openpyxl') as writer:
            # Put Unassigned last; suppliers sorted alphabetically
            ordered = sorted([k for k in groups.keys() if k != 'Unassigned'])
            if 'Unassigned' in groups:
                ordered.append('Unassigned')
            for sname in ordered:
                name = _safe_sheet_name(sname)
                final = name
                idx = 1
                while final in used_names:
                    suffix = f" ({idx})"
                    final = _safe_sheet_name(name[:31 - len(suffix)] + suffix)
                    idx += 1
                used_names.add(final)
                df = pd.DataFrame(groups[sname])
                df.to_excel(writer, sheet_name=final, index=False)
                _autosize_worksheet(writer.sheets[final])

        buffer.seek(0)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(
            buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'approved_items_by_supplier_{ts}.xlsx'
        )
    except Exception as e:
        print(f"DEBUG: export_approved_by_supplier error: {e}")
        traceback.print_exc()
        return jsonify(success=False, error=str(e)), 500


@app.route('/api/operations/approved-items/export/request/<int:request_id>', methods=['GET'])
@perm('approved_item.view')
def export_approved_single_request(request_id):
    """Excel file with a single sheet listing all approved items for one request."""
    try:
        rows = _approved_items_fetch_all()
        rows = [r for r in rows if r['request_id'] == request_id]
        if not rows:
            return jsonify(success=False, error='No approved items found for this request'), 404
        title = rows[0].get('request_title') or ''
        items = [_approved_item_row_to_dict(r) for r in rows]

        buffer = BytesIO()
        with ExcelWriter(buffer, engine='openpyxl') as writer:
            sheet_name = _safe_sheet_name(f"Req {request_id} - {title}" if title else f"Request {request_id}")
            df = pd.DataFrame(items)
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            _autosize_worksheet(writer.sheets[sheet_name])

        buffer.seek(0)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(
            buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'approved_items_request_{request_id}_{ts}.xlsx'
        )
    except Exception as e:
        print(f"DEBUG: export_approved_single_request error: {e}")
        traceback.print_exc()
        return jsonify(success=False, error=str(e)), 500


# ===================== APPROVED ITEM COMPONENTS API =====================

@app.route('/api/approved-items/<int:item_id>/components', methods=['GET'])
@perm('approved_item.view')
def get_item_components(item_id):
    """Get all components for an approved item"""
    try:
        conn, cur = connection()
        
        cur.execute("""
            SELECT 
                c.*,
                s.supplier_name,
                s.primary_phone as supplier_phone,
                s.email_address as supplier_email,
                u.name as received_by_name,
                creator.name as created_by_name
            FROM approved_item_components c
            LEFT JOIN supplier s ON c.supplier_id = s.id
            LEFT JOIN user u ON c.received_by = u.id
            LEFT JOIN user creator ON c.created_by = creator.id
            WHERE c.sales_item_id = %s
            ORDER BY c.created_at DESC
        """, (item_id,))
        
        components = cur.fetchall()
        
        # Also get the main item's direct supplier info (for items without components)
        cur.execute("""
            SELECT 
                i.supplier_id,
                i.supplier_due_date,
                i.supplier_received_date,
                i.supplier_received_by,
                i.has_components,
                s.supplier_name,
                s.primary_phone as supplier_phone,
                u.name as received_by_name
            FROM sales_request_items i
            LEFT JOIN supplier s ON i.supplier_id = s.id
            LEFT JOIN user u ON i.supplier_received_by = u.id
            WHERE i.id = %s
        """, (item_id,))
        
        item_supplier = cur.fetchone()
        
        cur.close()
        conn.close()
        
        # Format dates
        components_list = []
        for comp in components:
            components_list.append({
                'id': comp['id'],
                'sales_item_id': comp['sales_item_id'],
                'component_name': comp['component_name'],
                'description': comp['description'],
                'supplier_id': comp['supplier_id'],
                'supplier_name': comp['supplier_name'],
                'supplier_phone': comp['supplier_phone'],
                'supplier_email': comp['supplier_email'],
                'due_date': comp['due_date'].isoformat() if comp['due_date'] else None,
                'received_date': comp['received_date'].isoformat() if comp['received_date'] else None,
                'received_by': comp['received_by'],
                'received_by_name': comp['received_by_name'],
                'status': comp['status'],
                'notes': comp['notes'],
                'created_at': comp['created_at'].isoformat() if comp['created_at'] else None,
                'created_by_name': comp['created_by_name']
            })
        
        item_info = None
        if item_supplier:
            item_info = {
                'supplier_id': item_supplier['supplier_id'],
                'supplier_name': item_supplier['supplier_name'],
                'supplier_phone': item_supplier['supplier_phone'],
                'supplier_due_date': item_supplier['supplier_due_date'].isoformat() if item_supplier['supplier_due_date'] else None,
                'supplier_received_date': item_supplier['supplier_received_date'].isoformat() if item_supplier['supplier_received_date'] else None,
                'supplier_received_by': item_supplier['supplier_received_by'],
                'received_by_name': item_supplier['received_by_name'],
                'has_components': bool(item_supplier['has_components'])
            }
        
        return jsonify({
            'success': True,
            'components': components_list,
            'item_supplier_info': item_info
        })
        
    except Exception as e:
        print(f"Error fetching item components: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/approved-items/<int:item_id>/components', methods=['POST'])
@perm('approved_item.edit')
def add_item_component(item_id):
    """Add a component to an approved item"""
    try:
        data = request.get_json()
        
        component_name = data.get('component_name')
        description = data.get('description', '')
        supplier_id = data.get('supplier_id')
        due_date = data.get('due_date')
        notes = data.get('notes', '')
        
        if not component_name:
            return jsonify({'success': False, 'error': 'Component name is required'}), 400
        
        conn, cur = connection()
        
        # Insert the component
        cur.execute("""
            INSERT INTO approved_item_components 
            (sales_item_id, component_name, description, supplier_id, due_date, notes, created_by, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (item_id, component_name, description, supplier_id, due_date, notes, session.get('user_id')))
        
        component_id = cur.lastrowid
        
        # Update the parent item to indicate it has components
        cur.execute("""
            UPDATE sales_request_items SET has_components = 1 WHERE id = %s
        """, (item_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Component added successfully',
            'component_id': component_id
        })
        
    except Exception as e:
        print(f"Error adding component: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/approved-items/components/<int:component_id>', methods=['PUT'])
@perm('approved_item.edit')
def update_item_component(component_id):
    """Update a component"""
    try:
        data = request.get_json()
        
        conn, cur = connection()
        
        # Build dynamic update query
        update_fields = []
        update_values = []
        
        allowed_fields = ['component_name', 'description', 'supplier_id', 'due_date', 'received_date', 'status', 'notes']
        
        for field in allowed_fields:
            if field in data:
                update_fields.append(f"{field} = %s")
                update_values.append(data[field] if data[field] != '' else None)
        
        # Handle received_by separately - set current user when marking received
        if data.get('status') == 'received' and data.get('received_date'):
            update_fields.append("received_by = %s")
            update_values.append(session.get('user_id'))
        
        if not update_fields:
            return jsonify({'success': False, 'error': 'No fields to update'}), 400
        
        update_values.append(component_id)
        
        cur.execute(f"""
            UPDATE approved_item_components 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """, update_values)
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Component updated successfully'
        })
        
    except Exception as e:
        print(f"Error updating component: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/approved-items/components/<int:component_id>', methods=['DELETE'])
@perm('approved_item.edit')
def delete_item_component(component_id):
    """Delete a component"""
    try:
        conn, cur = connection()
        
        # Get the parent item ID first
        cur.execute("SELECT sales_item_id FROM approved_item_components WHERE id = %s", (component_id,))
        comp = cur.fetchone()
        
        if not comp:
            return jsonify({'success': False, 'error': 'Component not found'}), 404
        
        sales_item_id = comp['sales_item_id']
        
        # Delete the component
        cur.execute("DELETE FROM approved_item_components WHERE id = %s", (component_id,))
        
        # Check if there are any remaining components
        cur.execute("SELECT COUNT(*) as count FROM approved_item_components WHERE sales_item_id = %s", (sales_item_id,))
        remaining = cur.fetchone()
        
        # If no more components, update has_components flag
        if remaining['count'] == 0:
            cur.execute("UPDATE sales_request_items SET has_components = 0 WHERE id = %s", (sales_item_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Component deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting component: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/approved-items/<int:item_id>/supplier', methods=['PUT'])
@perm('approved_item.edit')
def update_item_supplier(item_id):
    """Update supplier info for an item without components (direct assignment)"""
    try:
        data = request.get_json()
        
        supplier_id = data.get('supplier_id')
        due_date = data.get('due_date')
        received_date = data.get('received_date')
        
        conn, cur = connection()
        
        # Build update query
        update_fields = ['supplier_id = %s', 'supplier_due_date = %s']
        update_values = [supplier_id if supplier_id else None, due_date if due_date else None]
        
        if received_date:
            update_fields.append('supplier_received_date = %s')
            update_values.append(received_date)
            update_fields.append('supplier_received_by = %s')
            update_values.append(session.get('user_id'))
        
        update_values.append(item_id)
        
        cur.execute(f"""
            UPDATE sales_request_items 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """, update_values)
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Item supplier info updated successfully'
        })
        
    except Exception as e:
        print(f"Error updating item supplier: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/suppliers/list', methods=['GET'])
@perm('supplier.view')
def get_suppliers_list():
    """Get list of all active suppliers for dropdown"""
    try:
        conn, cur = connection()
        
        cur.execute("""
            SELECT id, supplier_name, company_name, primary_phone, email_address
            FROM supplier
            WHERE status = 'Active'
            ORDER BY supplier_name
        """)
        
        suppliers = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'suppliers': suppliers
        })
        
    except Exception as e:
        print(f"Error fetching suppliers: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ===================== SUPPLIER REPORT =====================

@app.route('/supplier-report', methods=['GET'])
@perm('supplier_report.view')
def supplier_report_page():
    """Display supplier report page"""
    return render_template("supplier_report.html")


@app.route('/api/supplier-report', methods=['GET'])
@perm('supplier_report.view')
def get_supplier_report():
    """Get comprehensive supplier report with all related items and components"""
    try:
        supplier_id = request.args.get('supplier_id')
        status_filter = request.args.get('status', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        item_type = request.args.get('item_type', '')  # 'direct' or 'component'
        request_start_from = request.args.get('request_start_from', '')
        request_start_to = request.args.get('request_start_to', '')
        request_end_from = request.args.get('request_end_from', '')
        request_end_to = request.args.get('request_end_to', '')
        
        print(f"DEBUG Supplier Report Filters: request_start_from={request_start_from}, request_start_to={request_start_to}, request_end_from={request_end_from}, request_end_to={request_end_to}")
        
        conn, cur = connection()
        
        # Get all suppliers with statistics
        query = """
            SELECT 
                s.id,
                s.supplier_name,
                s.company_name,
                s.primary_phone,
                s.email_address,
                s.status,
                s.address,
                s.supplier_type,
                COUNT(DISTINCT sri.id) as direct_items_count,
                COUNT(DISTINCT aic.id) as components_count,
                SUM(CASE WHEN aic.status = 'pending' THEN 1 ELSE 0 END) as pending_count,
                SUM(CASE WHEN aic.status = 'ordered' THEN 1 ELSE 0 END) as ordered_count,
                SUM(CASE WHEN aic.status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_count,
                SUM(CASE WHEN aic.status = 'received' THEN 1 ELSE 0 END) as received_count
            FROM supplier s
            LEFT JOIN sales_request_items sri ON s.id = sri.supplier_id AND sri.approval_status = 'approved'
            LEFT JOIN approved_item_components aic ON s.id = aic.supplier_id
        """
        
        where_clauses = []
        params = []
        
        if supplier_id:
            where_clauses.append("s.id = %s")
            params.append(supplier_id)
        
        if status_filter:
            where_clauses.append("s.status = %s")
            params.append(status_filter)
        
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        query += " GROUP BY s.id ORDER BY s.supplier_name"
        
        cur.execute(query, params)
        suppliers = cur.fetchall()
        
        # Get detailed items for each supplier or all if specific supplier
        items_query = """
            SELECT 
                'direct' as assignment_type,
                sri.id as item_id,
                sri.name as item_name,
                sri.description,
                sri.qty,
                sri.unit,
                sri.total_cost,
                sri.total_sell,
                sri.supplier_due_date as due_date,
                sri.supplier_received_date as received_date,
                CASE WHEN sri.supplier_received_date IS NOT NULL THEN 'received' ELSE 'pending' END as status,
                sr.id as request_id,
                sr.title as request_title,
                sr.start_date as request_start_date,
                sr.end_date as request_end_date,
                c.client_name,
                s.id as supplier_id,
                s.supplier_name,
                u.name as received_by_name
            FROM sales_request_items sri
            INNER JOIN sales_request sr ON sri.request_id = sr.id
            LEFT JOIN client c ON sr.client_id = c.id
            LEFT JOIN supplier s ON sri.supplier_id = s.id
            LEFT JOIN user u ON sri.supplier_received_by = u.id
            WHERE sri.approval_status = 'approved'
        """
        
        components_query = """
            SELECT 
                'component' as assignment_type,
                aic.id as item_id,
                aic.component_name as item_name,
                aic.description,
                1 as qty,
                'pcs' as unit,
                NULL as total_cost,
                NULL as total_sell,
                aic.due_date,
                aic.received_date,
                aic.status,
                sri.request_id,
                sr.title as request_title,
                sr.start_date as request_start_date,
                sr.end_date as request_end_date,
                c.client_name,
                s.id as supplier_id,
                s.supplier_name,
                u.name as received_by_name
            FROM approved_item_components aic
            INNER JOIN sales_request_items sri ON aic.sales_item_id = sri.id
            INNER JOIN sales_request sr ON sri.request_id = sr.id
            LEFT JOIN client c ON sr.client_id = c.id
            LEFT JOIN supplier s ON aic.supplier_id = s.id
            LEFT JOIN user u ON aic.received_by = u.id
            WHERE 1=1
        """
        
        # Add supplier filter if specified
        items_params = []
        components_params = []
        
        if supplier_id:
            if supplier_id == 'unassigned':
                items_query += " AND sri.supplier_id IS NULL"
                components_query += " AND aic.supplier_id IS NULL"
            else:
                items_query += " AND sri.supplier_id = %s"
                items_params.append(supplier_id)
                components_query += " AND aic.supplier_id = %s"
                components_params.append(supplier_id)
        
        # Add date filters - handle NULL due dates properly
        if date_from and date_to:
            # Both dates provided - filter within range (include items with NULL due dates too)
            items_query += " AND (sri.supplier_due_date >= %s AND sri.supplier_due_date <= %s)"
            items_params.extend([date_from, date_to])
            components_query += " AND (aic.due_date >= %s AND aic.due_date <= %s)"
            components_params.extend([date_from, date_to])
        elif date_from:
            # Only from date - show items from this date onwards
            items_query += " AND (sri.supplier_due_date >= %s OR sri.supplier_due_date IS NULL)"
            items_params.append(date_from)
            components_query += " AND (aic.due_date >= %s OR aic.due_date IS NULL)"
            components_params.append(date_from)
        elif date_to:
            # Only to date - show items up to this date (include NULL as they have no due date yet)
            items_query += " AND (sri.supplier_due_date <= %s OR sri.supplier_due_date IS NULL)"
            items_params.append(date_to)
            components_query += " AND (aic.due_date <= %s OR aic.due_date IS NULL)"
            components_params.append(date_to)
        
        # Add status filter for items
        if status_filter:
            # For direct items, use supplier_received_date to determine status
            if status_filter == 'received':
                items_query += " AND sri.supplier_received_date IS NOT NULL"
            elif status_filter == 'pending':
                items_query += " AND sri.supplier_received_date IS NULL"
            # For ordered/in_progress, direct items don't have this status tracked, so exclude them
            elif status_filter in ['ordered', 'in_progress']:
                items_query += " AND 1=0"  # No direct items match these statuses
            
            # For components, filter by the actual status column
            components_query += " AND aic.status = %s"
            components_params.append(status_filter)
        
        # Add request start date filter
        if request_start_from:
            items_query += " AND sr.start_date >= %s"
            items_params.append(request_start_from)
            components_query += " AND sr.start_date >= %s"
            components_params.append(request_start_from)
        
        if request_start_to:
            items_query += " AND sr.start_date <= %s"
            items_params.append(request_start_to)
            components_query += " AND sr.start_date <= %s"
            components_params.append(request_start_to)
        
        # Add request end date filter
        if request_end_from:
            items_query += " AND sr.end_date >= %s"
            items_params.append(request_end_from)
            components_query += " AND sr.end_date >= %s"
            components_params.append(request_end_from)
        
        if request_end_to:
            items_query += " AND sr.end_date <= %s"
            items_params.append(request_end_to)
            components_query += " AND sr.end_date <= %s"
            components_params.append(request_end_to)
        
        # Fetch based on item_type filter
        direct_items = []
        component_items = []
        
        print(f"DEBUG item_type filter: '{item_type}'")
        
        if item_type != 'component':
            print(f"DEBUG Executing items_query with params: {items_params}")
            cur.execute(items_query, items_params)
            direct_items = cur.fetchall()
            print(f"DEBUG Found {len(direct_items)} direct items")
        
        if item_type != 'direct':
            print(f"DEBUG Executing components_query with params: {components_params}")
            cur.execute(components_query, components_params)
            component_items = cur.fetchall()
            print(f"DEBUG Found {len(component_items)} component items")
        
        cur.close()
        conn.close()
        
        # Process results
        suppliers_list = []
        for s in suppliers:
            suppliers_list.append({
                'id': s['id'],
                'supplier_name': s['supplier_name'],
                'company_name': s['company_name'],
                'primary_phone': s['primary_phone'],
                'email_address': s['email_address'],
                'status': s['status'],
                'address': s['address'],
                'supplier_type': s['supplier_type'],
                'direct_items_count': s['direct_items_count'] or 0,
                'components_count': s['components_count'] or 0,
                'pending_count': int(s['pending_count'] or 0),
                'ordered_count': int(s['ordered_count'] or 0),
                'in_progress_count': int(s['in_progress_count'] or 0),
                'received_count': int(s['received_count'] or 0)
            })
        
        items_list = []
        for item in direct_items + component_items:
            items_list.append({
                'assignment_type': item['assignment_type'],
                'item_id': item['item_id'],
                'item_name': item['item_name'],
                'description': item['description'],
                'qty': float(item['qty']) if item['qty'] else 1,
                'unit': item['unit'] or 'pcs',
                'total_cost': float(item['total_cost']) if item['total_cost'] else None,
                'total_sell': float(item['total_sell']) if item['total_sell'] else None,
                'due_date': item['due_date'].isoformat() if item['due_date'] else None,
                'received_date': item['received_date'].isoformat() if item['received_date'] else None,
                'status': item['status'],
                'request_id': item['request_id'],
                'request_title': item['request_title'],
                'request_start_date': item['request_start_date'].isoformat() if item['request_start_date'] else None,
                'request_end_date': item['request_end_date'].isoformat() if item['request_end_date'] else None,
                'client_name': item['client_name'],
                'supplier_id': item['supplier_id'],
                'supplier_name': item['supplier_name'],
                'received_by_name': item['received_by_name']
            })
        
        return jsonify({
            'success': True,
            'suppliers': suppliers_list,
            'items': items_list,
            'stats': {
                'total_suppliers': len(suppliers_list),
                'total_items': len(items_list),
                'pending': sum(1 for i in items_list if i['status'] == 'pending'),
                'received': sum(1 for i in items_list if i['status'] == 'received')
            }
        })
        
    except Exception as e:
        print(f"Error fetching supplier report: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/supplier-report/scorecards', methods=['GET'])
@perm('supplier_report.view')
def get_supplier_scorecards():
    """Lightweight per-supplier scorecards: on-time %, total received, avg lead-time (days).
    Aggregates components (approved_item_components) + direct items (sales_request_items).
    """
    try:
        conn, cur = connection()

        # Direct items: lead time = supplier_received_date - sr.start_date
        cur.execute("""
            SELECT 
                s.id AS supplier_id,
                s.supplier_name,
                COUNT(CASE WHEN sri.supplier_received_date IS NOT NULL THEN 1 END) AS direct_received,
                COUNT(CASE WHEN sri.supplier_received_date IS NOT NULL 
                            AND sri.supplier_due_date IS NOT NULL 
                            AND sri.supplier_received_date <= sri.supplier_due_date THEN 1 END) AS direct_on_time,
                COUNT(CASE WHEN sri.supplier_received_date IS NOT NULL 
                            AND sri.supplier_due_date IS NOT NULL THEN 1 END) AS direct_due_received,
                AVG(CASE WHEN sri.supplier_received_date IS NOT NULL AND sr.start_date IS NOT NULL
                         THEN DATEDIFF(sri.supplier_received_date, sr.start_date) END) AS direct_avg_lead
            FROM supplier s
            LEFT JOIN sales_request_items sri 
                ON sri.supplier_id = s.id AND sri.approval_status = 'approved'
            LEFT JOIN sales_request sr ON sr.id = sri.request_id
            GROUP BY s.id, s.supplier_name
        """)
        direct_rows = {r['supplier_id']: r for r in cur.fetchall()}

        # Components: lead time = received_date - aic.created_at::date
        cur.execute("""
            SELECT 
                s.id AS supplier_id,
                COUNT(CASE WHEN aic.received_date IS NOT NULL THEN 1 END) AS comp_received,
                COUNT(CASE WHEN aic.received_date IS NOT NULL 
                            AND aic.due_date IS NOT NULL 
                            AND aic.received_date <= aic.due_date THEN 1 END) AS comp_on_time,
                COUNT(CASE WHEN aic.received_date IS NOT NULL 
                            AND aic.due_date IS NOT NULL THEN 1 END) AS comp_due_received,
                AVG(CASE WHEN aic.received_date IS NOT NULL AND aic.created_at IS NOT NULL
                         THEN DATEDIFF(aic.received_date, DATE(aic.created_at)) END) AS comp_avg_lead
            FROM supplier s
            LEFT JOIN approved_item_components aic ON aic.supplier_id = s.id
            GROUP BY s.id
        """)
        comp_rows = {r['supplier_id']: r for r in cur.fetchall()}

        cur.close(); conn.close()

        scorecards = []
        for sid, d in direct_rows.items():
            c = comp_rows.get(sid, {})
            total_received = int((d.get('direct_received') or 0)) + int((c.get('comp_received') or 0))
            if total_received == 0:
                continue
            on_time = int((d.get('direct_on_time') or 0)) + int((c.get('comp_on_time') or 0))
            due_received = int((d.get('direct_due_received') or 0)) + int((c.get('comp_due_received') or 0))
            on_time_pct = round((on_time / due_received) * 100, 1) if due_received > 0 else None

            # Weighted avg lead time
            leads = []
            if d.get('direct_avg_lead') is not None and (d.get('direct_received') or 0) > 0:
                leads.append((float(d['direct_avg_lead']), int(d['direct_received'])))
            if c.get('comp_avg_lead') is not None and (c.get('comp_received') or 0) > 0:
                leads.append((float(c['comp_avg_lead']), int(c['comp_received'])))
            if leads:
                num = sum(v * w for v, w in leads); den = sum(w for _, w in leads)
                avg_lead = round(num / den, 1) if den > 0 else None
            else:
                avg_lead = None

            scorecards.append({
                'supplier_id': sid,
                'supplier_name': d.get('supplier_name') or 'Unknown',
                'total_received': total_received,
                'on_time_pct': on_time_pct,
                'avg_lead_time_days': avg_lead,
            })

        scorecards.sort(key=lambda x: (-(x['total_received'] or 0), -(x['on_time_pct'] or 0)))
        return jsonify({'success': True, 'scorecards': scorecards})
    except Exception as e:
        print(f"Error fetching supplier scorecards: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/supplier-report/export-excel', methods=['GET'])
@perm('supplier_report.view')
def export_supplier_report_excel():
    """Export the current supplier-report (filtered) to an Excel workbook.
    Two sheets: 'All Items' and one sheet per supplier.
    Reuses the same filter parameters as /api/supplier-report.
    """
    try:
        # Re-use the same fetch by calling the function logic isn't trivial; do a direct call
        # via internal Flask test client to keep behavior consistent.
        from flask import request as _req
        # Snapshot the session before entering the inner context: inside the
        # `with`, `session` already refers to the new, empty one, so copying
        # there copies nothing and the inner call sees an anonymous caller.
        _outer_session = dict(session)
        with app.test_request_context(
            '/api/supplier-report?' + _req.query_string.decode('utf-8'),
            method='GET'
        ):
            from flask import session as _sess
            _sess.update(_outer_session)
            resp = get_supplier_report()
        # resp is a tuple or Response
        if isinstance(resp, tuple):
            payload = resp[0].get_json()
        else:
            payload = resp.get_json()
        if not payload or not payload.get('success'):
            return jsonify(success=False, error=(payload or {}).get('error', 'Failed to load report')), 500

        items = payload.get('items') or []
        if not items:
            return jsonify(success=False, error='No items to export'), 404

        def _row(i):
            return {
                'Request #': i.get('request_id'),
                'Request Title': i.get('request_title'),
                'Client': i.get('client_name'),
                'Supplier': i.get('supplier_name') or 'Unassigned',
                'Assignment': i.get('assignment_type'),
                'Item': i.get('item_name'),
                'Description': i.get('description'),
                'Qty': i.get('qty'),
                'Unit': i.get('unit'),
                'Cost': i.get('total_cost'),
                'Due Date': i.get('due_date'),
                'Received Date': i.get('received_date'),
                'Status': i.get('status'),
                'Received By': i.get('received_by_name'),
                'Request Start': i.get('request_start_date'),
                'Request End': i.get('request_end_date'),
            }

        buffer = BytesIO()
        with ExcelWriter(buffer, engine='openpyxl') as writer:
            df_all = pd.DataFrame([_row(i) for i in items])
            df_all.to_excel(writer, sheet_name='All Items', index=False)
            _autosize_worksheet(writer.sheets['All Items'])

            groups = {}
            for i in items:
                key = i.get('supplier_name') or 'Unassigned'
                groups.setdefault(key, []).append(i)
            used = {'All Items'}
            for name, lst in groups.items():
                sname = _safe_sheet_name(name)
                final = sname; idx = 1
                while final in used:
                    suffix = f" ({idx})"
                    final = _safe_sheet_name(sname[:31 - len(suffix)] + suffix); idx += 1
                used.add(final)
                df = pd.DataFrame([_row(i) for i in lst])
                df.to_excel(writer, sheet_name=final, index=False)
                _autosize_worksheet(writer.sheets[final])

        buffer.seek(0)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(
            buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'supplier_report_{ts}.xlsx'
        )
    except Exception as e:
        print(f"DEBUG: export_supplier_report_excel error: {e}")
        traceback.print_exc()
        return jsonify(success=False, error=str(e)), 500


@app.route('/company', methods=['GET'])
@perm('company.view')
def company():
    """Display company page - Admin or company_management role"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template("company.html")

@app.route('/api/companies', methods=['GET'])
@perm('company.view')
def get_companies():
    """API endpoint to fetch all companies - Admin only"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Fetch all companies with user info
        cur.execute("""
            SELECT c.*, 
                   c.added_by as added_by_name,
                   c.modified_by as modified_by_name
            FROM company c
            ORDER BY c.id DESC
        """)
        companies_data = cur.fetchall()
        
        # Convert to list of dictionaries for JSON response
        companies_list = []
        for company in companies_data:
            companies_list.append({
                'id': company['id'],
                'company_name': company['company_name'],
                'industry_sector': company['industry_sector'],
                'address': company['address'],
                'tax_number': company['tax_number'],
                'vat_number': company['vat_number'],
                'phone_number': company['phone_number'],
                'email_address': company['email_address'],
                'website_social_media': company['website_social_media'],
                'primary_contact_person': company['primary_contact_person'],
                'additional_notes': company['additional_notes'],
                'documents_path': company['documents_path'],
                'added_by': company['added_by'],
                'added_by_name': company['added_by_name'],
                'added_date': company['added_date'].strftime('%Y-%m-%d %H:%M:%S') if company['added_date'] else 'N/A',
                'modified_by': company['modified_by'],
                'modified_by_name': company['modified_by_name'],
                'modified_date': company['modified_date'].strftime('%Y-%m-%d %H:%M:%S') if company['modified_date'] else 'N/A'
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'companies': companies_list
        })
    except Exception as e:
        print(e)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/companies/add', methods=['POST'])
@perm('company.create')
def add_company():
    """API endpoint to add a new company - Admin or company_management role"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        # Debug logging
        print(f"DEBUG: add_company called")
        print(f"DEBUG: request.is_json: {request.is_json}")
        print(f"DEBUG: request.content_type: {request.content_type}")
        
        # Handle both JSON and FormData
        if request.is_json:
            data = request.get_json()
            files = []
            print(f"DEBUG: JSON data received: {data}")
        else:
            data = request.form.to_dict()
            files = request.files.getlist('documents')
            print(f"DEBUG: Form data received: {data}")
            print(f"DEBUG: Files received: {[f.filename for f in files]}")

        # Parse attachment links (optional JSON array of {label, url})
        document_links = []
        try:
            raw_links = data.get('document_links') if isinstance(data, dict) else None
            if raw_links:
                parsed = json.loads(raw_links) if isinstance(raw_links, str) else raw_links
                if isinstance(parsed, list):
                    for entry in parsed:
                        url = (entry.get('url') or '').strip()
                        if not url:
                            continue
                        label = (entry.get('label') or url).strip()
                        document_links.append({'label': label, 'url': url})
        except Exception as link_err:
            print(f"DEBUG: Failed to parse document_links: {link_err}")

        # Validate required fields
        required_fields = ['company_name', 'industry_sector', 'address', 
                          'phone_number', 'email_address', 'primary_contact_person']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        conn, cur = connection()
        
        # Check if company name already exists
        cur.execute("SELECT id FROM company WHERE company_name = %s", (data['company_name'],))
        if cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'Company name already exists'
            }), 400
        
        # Check if tax number already exists (if provided)
        if data.get('tax_number'):
            cur.execute("SELECT id FROM company WHERE tax_number = %s", (data['tax_number'],))
            if cur.fetchone():
                return jsonify({
                    'success': False,
                    'error': 'Tax number already exists'
                }), 400
        
        # Check if VAT number already exists (if provided)
        if data.get('vat_number'):
            cur.execute("SELECT id FROM company WHERE vat_number = %s", (data['vat_number'],))
            if cur.fetchone():
                return jsonify({
                    'success': False,
                    'error': 'VAT number already exists'
                }), 400
        
        # Validate document requirement (files OR links count)
        has_tax_or_vat = data.get('tax_number') or data.get('vat_number')
        if has_tax_or_vat and len(files) == 0 and len(document_links) == 0:
            return jsonify({
                'success': False,
                'error': 'Documents are required when Tax Number or VAT Number is provided'
            }), 400
        
        # Insert new company
        cur.execute("""
            INSERT INTO company (company_name, industry_sector, address, tax_number, vat_number,
                               phone_number, email_address, website_social_media, 
                               primary_contact_person, additional_notes, added_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data['company_name'],
            data['industry_sector'],
            data['address'],
            data.get('tax_number') or None,
            data.get('vat_number') or None,
            data['phone_number'],
            data['email_address'],
            data.get('website_social_media', ''),
            data['primary_contact_person'],
            data.get('additional_notes', ''),
            session['username']
        ))
        
        company_id = cur.lastrowid
        
        # Handle file uploads
        if files:
            # Validate file sizes first
            invalid_files = []
            for file in files:
                if file and file.filename:
                    if not validate_file_size(file):
                        invalid_files.append(file.filename)
            
            if invalid_files:
                return jsonify({
                    'success': False,
                    'error': f'The following files exceed the 20MB limit: {", ".join(invalid_files)}'
                }), 400
            
            upload_folder = f'uploads/companies/{company_id}'
            os.makedirs(upload_folder, exist_ok=True)
            
            for file in files:
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    timestamp = int(time.time())
                    unique_filename = f"{timestamp}_{filename}"
                    file_path = os.path.join(upload_folder, unique_filename)
                    file.save(file_path)
                    
                    # Insert document record
                    cur.execute("""
                        INSERT INTO company_documents (company_id, document_name, document_path, 
                                                     file_size, uploaded_by)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        company_id,
                        filename,
                        file_path,
                        os.path.getsize(file_path),
                        session['user_id']
                    ))

        # Insert attachment links as document rows (document_type='link')
        for link in document_links:
            cur.execute("""
                INSERT INTO company_documents (company_id, document_name, document_path,
                                             document_type, file_size, uploaded_by)
                VALUES (%s, %s, %s, 'link', 0, %s)
            """, (
                company_id,
                link['label'],
                link['url'],
                session['user_id']
            ))

        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Company added successfully'
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"DEBUG: Error in add_company: {e}")
        print(f"DEBUG: Full traceback: {error_details}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/companies/edit/<int:company_id>', methods=['POST'])
@perm('company.edit')
def edit_company(company_id):
    """API endpoint to edit an existing company - Admin or company_management role"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401

    try:
        # Handle both JSON and FormData
        if request.is_json:
            data = request.get_json()
            files = []
        else:
            data = request.form.to_dict()
            files = request.files.getlist('documents')

        # Parse attachment links (optional JSON array of {label, url})
        document_links = []
        try:
            raw_links = data.get('document_links') if isinstance(data, dict) else None
            if raw_links:
                parsed = json.loads(raw_links) if isinstance(raw_links, str) else raw_links
                if isinstance(parsed, list):
                    for entry in parsed:
                        url = (entry.get('url') or '').strip()
                        if not url:
                            continue
                        label = (entry.get('label') or url).strip()
                        document_links.append({'label': label, 'url': url})
        except Exception as link_err:
            print(f"DEBUG: Failed to parse document_links (edit): {link_err}")

        # Validate required fields
        required_fields = ['company_name', 'industry_sector', 'address', 
                          'phone_number', 'email_address', 'primary_contact_person']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400

        conn, cur = connection()

        # Check for duplicate company name
        cur.execute("SELECT id FROM company WHERE company_name = %s AND id != %s", (data['company_name'], company_id))
        if cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'Company name already exists'
            }), 400

        # Check for duplicate tax number (if provided)
        if data.get('tax_number'):
            cur.execute("SELECT id FROM company WHERE tax_number = %s AND id != %s", (data['tax_number'], company_id))
            if cur.fetchone():
                return jsonify({
                    'success': False,
                    'error': 'Tax number already exists'
                }), 400

        # Check for duplicate VAT number (if provided)
        if data.get('vat_number'):
            cur.execute("SELECT id FROM company WHERE vat_number = %s AND id != %s", (data['vat_number'], company_id))
            if cur.fetchone():
                return jsonify({
                    'success': False,
                    'error': 'VAT number already exists'
                }), 400

        # Update company details
        cur.execute("""
            UPDATE company
            SET company_name = %s, industry_sector = %s, address = %s, tax_number = %s, vat_number = %s,
                phone_number = %s, email_address = %s, website_social_media = %s,
                primary_contact_person = %s, additional_notes = %s, modified_by = %s
            WHERE id = %s
        """, (
            data['company_name'],
            data['industry_sector'],
            data['address'],
            data.get('tax_number') or None,
            data.get('vat_number') or None,
            data['phone_number'],
            data['email_address'],
            data.get('website_social_media', ''),
            data['primary_contact_person'],
            data.get('additional_notes', ''),
            session['username'],
            company_id
        ))
        
        # Handle new file uploads
        if files:
            # Validate file sizes first
            invalid_files = []
            for file in files:
                if file and file.filename:
                    if not validate_file_size(file):
                        invalid_files.append(file.filename)
            
            if invalid_files:
                return jsonify({
                    'success': False,
                    'error': f'The following files exceed the 20MB limit: {", ".join(invalid_files)}'
                }), 400
            
            upload_folder = f'uploads/companies/{company_id}'
            os.makedirs(upload_folder, exist_ok=True)
            
            for file in files:
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    timestamp = int(time.time())
                    unique_filename = f"{timestamp}_{filename}"
                    file_path = os.path.join(upload_folder, unique_filename)
                    file.save(file_path)
                    
                    # Insert document record
                    cur.execute("""
                        INSERT INTO company_documents (company_id, document_name, document_path, 
                                                     file_size, uploaded_by)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        company_id,
                        filename,
                        file_path,
                        os.path.getsize(file_path),
                        session['user_id']
                    ))

        # Insert any new attachment links
        for link in document_links:
            cur.execute("""
                INSERT INTO company_documents (company_id, document_name, document_path,
                                             document_type, file_size, uploaded_by)
                VALUES (%s, %s, %s, 'link', 0, %s)
            """, (
                company_id,
                link['label'],
                link['url'],
                session['user_id']
            ))

        # Validate document requirement after update
        has_tax_or_vat = data.get('tax_number') or data.get('vat_number')
        if has_tax_or_vat:
            # Check if company has any documents after update
            cur.execute("SELECT COUNT(*) as doc_count FROM company_documents WHERE company_id = %s", (company_id,))
            doc_count_result = cur.fetchone()
            doc_count = doc_count_result['doc_count'] if doc_count_result else 0
            
            if doc_count == 0:
                return jsonify({
                    'success': False,
                    'error': 'Documents are required when Tax Number or VAT Number is provided'
                }), 400

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Company updated successfully'
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"DEBUG: Error in edit_company: {e}")
        print(f"DEBUG: Full traceback: {error_details}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/companies/delete/<int:company_id>', methods=['DELETE'])
@perm('company.delete')
def delete_company(company_id):
    """API endpoint to delete a company - Admin or company_management role"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Check if company exists
        cur.execute("SELECT id FROM company WHERE id = %s", (company_id,))
        if not cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'Company not found'
            }), 404
        
        # Get and delete associated documents
        cur.execute("SELECT document_path FROM company_documents WHERE company_id = %s", (company_id,))
        documents = cur.fetchall()
        
        for doc in documents:
            if os.path.exists(doc['document_path']):
                os.remove(doc['document_path'])
        
        # Delete company documents records (cascade will handle this automatically due to FK constraint)
        cur.execute("DELETE FROM company_documents WHERE company_id = %s", (company_id,))
        
        # Delete company folder if it exists
        company_folder = f'uploads/companies/{company_id}'
        if os.path.exists(company_folder):
            shutil.rmtree(company_folder)
        
        # Delete company
        cur.execute("DELETE FROM company WHERE id = %s", (company_id,))
        conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Company deleted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/companies/<int:company_id>/documents', methods=['GET'])
@perm('company.view')
def get_company_documents(company_id):
    """API endpoint to get documents for a company - Admin or company_management role"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Fetch documents for the company
        cur.execute("""
            SELECT cd.*, u.username as uploaded_by_name
            FROM company_documents cd
            LEFT JOIN user u ON cd.uploaded_by = u.id
            WHERE cd.company_id = %s
            ORDER BY cd.uploaded_date DESC
        """, (company_id,))
        
        documents = cur.fetchall()
        
        # Convert to list of dictionaries
        documents_list = []
        for doc in documents:
            documents_list.append({
                'id': doc['id'],
                'company_id': doc['company_id'],
                'document_name': doc['document_name'],
                'document_path': doc['document_path'],
                'document_type': doc['document_type'],
                'file_size': doc['file_size'],
                'uploaded_by': doc['uploaded_by'],
                'uploaded_by_name': doc['uploaded_by_name'],
                'uploaded_date': doc['uploaded_date'].strftime('%Y-%m-%d %H:%M:%S') if doc['uploaded_date'] else 'N/A'
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'documents': documents_list
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"DEBUG: Error in get_company_documents: {e}")
        print(f"DEBUG: Full traceback: {error_details}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/companies/documents/<int:document_id>', methods=['DELETE'])
@perm('company.edit')
def delete_company_document(document_id):
    """API endpoint to delete a company document - Admin or company_management role"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Get document info and company info before deletion
        cur.execute("""
            SELECT cd.document_path, cd.company_id, c.tax_number, c.vat_number
            FROM company_documents cd
            JOIN company c ON cd.company_id = c.id
            WHERE cd.id = %s
        """, (document_id,))
        result = cur.fetchone()
        
        if not result:
            return jsonify({
                'success': False,
                'error': 'Document not found'
            }), 404
        
        document_path = result['document_path']
        company_id = result['company_id']
        tax_number = result['tax_number']
        vat_number = result['vat_number']
        
        # Check if company has tax/VAT numbers
        has_tax_or_vat = bool(tax_number) or bool(vat_number)
        
        if has_tax_or_vat:
            # Count remaining documents for this company
            cur.execute("SELECT COUNT(*) as doc_count FROM company_documents WHERE company_id = %s", (company_id,))
            doc_count_result = cur.fetchone()
            remaining_docs = doc_count_result['doc_count'] if doc_count_result else 0
            
            # If this would be the last document, prevent deletion
            if remaining_docs <= 1:
                return jsonify({
                    'success': False,
                    'error': 'Cannot delete the last document. Companies with Tax Number or VAT Number must have at least one supporting document.'
                }), 400
        
        # Delete the physical file
        if os.path.exists(document_path):
            os.remove(document_path)
        
        # Delete from database
        cur.execute("DELETE FROM company_documents WHERE id = %s", (document_id,))
        conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Document deleted successfully'
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"DEBUG: Error in delete_company_document: {e}")
        print(f"DEBUG: Full traceback: {error_details}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/companies/documents/<int:document_id>/download', methods=['GET'])
@perm('company.view')
def download_company_document(document_id):
    """API endpoint to download a company document - Admin or company_management role"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Get document info
        cur.execute("SELECT document_name, document_path FROM company_documents WHERE id = %s", (document_id,))
        document = cur.fetchone()
        
        if not document:
            return jsonify({
                'success': False,
                'error': 'Document not found'
            }), 404
        
        cur.close()
        conn.close()
        
        document_path = document['document_path']
        document_name = document['document_name']
        
        # Check if file exists
        if not os.path.exists(document_path):
            return jsonify({
                'success': False,
                'error': 'Physical file not found'
            }), 404
        
        # Send file for download
        return send_file(
            document_path,
            as_attachment=True,
            download_name=document_name,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"DEBUG: Error in download_company_document: {e}")
        print(f"DEBUG: Full traceback: {error_details}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/client', methods=['GET'])
@perm('client.view')
def client():
    """Display client page - Admin or client_management role"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template("client.html")

@app.route('/api/clients', methods=['GET'])
@perm('client.view')
def get_clients():
    """API endpoint to fetch all clients"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Fetch all clients with company info
        cur.execute("""
            SELECT c.*, 
                   comp.company_name as parent_company_name,
                   c.added_by as added_by_name,
                   c.modified_by as modified_by_name
            FROM client c
            LEFT JOIN company comp ON c.parent_company_id = comp.id
            ORDER BY c.id DESC
        """)
        clients_data = cur.fetchall()
        
        # Convert to list of dictionaries for JSON response
        clients_list = []
        for client in clients_data:
            clients_list.append({
                'id': client['id'],
                'parent_company_id': client['parent_company_id'],
                'parent_company_name': client['parent_company_name'] or 'N/A',
                'client_name': client['client_name'],
                'mobile_number': client['mobile_number'],
                'secondary_mobile_number': client.get('secondary_mobile_number', ''),
                'email_address': client['email_address'],
                'job_title': client['job_title'] or '',
                'preferred_contact_channel': client['preferred_contact_channel'],
                'additional_notes': client['additional_notes'] or '',
                'added_by': client['added_by'],
                'added_by_name': client['added_by_name'],
                'added_date': client['added_date'].strftime('%Y-%m-%d %H:%M:%S') if client['added_date'] else 'N/A',
                'modified_by': client['modified_by'],
                'modified_by_name': client['modified_by_name'],
                'modified_date': client['modified_date'].strftime('%Y-%m-%d %H:%M:%S') if client['modified_date'] else 'N/A'
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'clients': clients_list
        })
    except Exception as e:
        print(e)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clients/add', methods=['POST'])
@perm('client.create')
def add_client():
    """API endpoint to add a new client - Admin or client_management role"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['client_name', 'mobile_number', 'email_address']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        conn, cur = connection()
        
        # Check if mobile number already exists
        cur.execute("SELECT id FROM client WHERE mobile_number = %s", (data['mobile_number'],))
        if cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'Mobile number already exists'
            }), 400
        
        # Check if email already exists
        cur.execute("SELECT id FROM client WHERE email_address = %s", (data['email_address'],))
        if cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'Email address already exists'
            }), 400
        
        # Validate parent company if provided
        parent_company_id = data.get('parent_company_id')
        if parent_company_id:
            cur.execute("SELECT id FROM company WHERE id = %s", (parent_company_id,))
            if not cur.fetchone():
                return jsonify({
                    'success': False,
                    'error': 'Invalid parent company selected'
                }), 400
        else:
            parent_company_id = None
        
        # Insert new client
        cur.execute("""
            INSERT INTO client (parent_company_id, client_name, mobile_number, secondary_mobile_number, 
                              email_address, job_title, preferred_contact_channel, additional_notes, added_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            parent_company_id,
            data['client_name'],
            data['mobile_number'],
            data.get('secondary_mobile_number', '') or None,
            data['email_address'],
            data.get('job_title', ''),
            data.get('preferred_contact_channel', 'Phone'),
            data.get('additional_notes', ''),
            session['username']
        ))
        
        conn.commit()
        
        # Get the newly inserted client ID
        client_id = cur.lastrowid
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Client added successfully',
            'client_id': client_id,
            'client_name': data['client_name']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clients/edit/<int:client_id>', methods=['POST'])
@perm('client.edit')
def edit_client(client_id):
    """API endpoint to edit an existing client - Admin or client_management role"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401

    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['client_name', 'mobile_number', 'email_address']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400

        conn, cur = connection()

        # Debug: Check current client data first
        cur.execute("SELECT mobile_number, email_address FROM client WHERE id = %s", (client_id,))
        current_client = cur.fetchone()
        if not current_client:
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404

        # Only check for duplicate mobile if it's different from current
        if data['mobile_number'] != current_client['mobile_number']:
            cur.execute("SELECT id FROM client WHERE mobile_number = %s", (data['mobile_number'],))
            duplicate_mobile = cur.fetchone()
            if duplicate_mobile:
                cur.close()
                conn.close()
                return jsonify({
                    'success': False,
                    'error': 'Mobile number already exists'
                }), 400

        # Only check for duplicate email if it's different from current
        if data['email_address'] != current_client['email_address']:
            cur.execute("SELECT id FROM client WHERE email_address = %s", (data['email_address'],))
            duplicate_email = cur.fetchone()
            if duplicate_email:
                cur.close()
                conn.close()
                return jsonify({
                    'success': False,
                    'error': 'Email address already exists'
                }), 400

        # Validate parent company if provided
        parent_company_id = data.get('parent_company_id')
        if parent_company_id:
            cur.execute("SELECT id FROM company WHERE id = %s", (parent_company_id,))
            if not cur.fetchone():
                return jsonify({
                    'success': False,
                    'error': 'Invalid parent company selected'
                }), 400
        else:
            parent_company_id = None

        # Update client details
        cur.execute("""
            UPDATE client
            SET parent_company_id = %s, client_name = %s, mobile_number = %s, secondary_mobile_number = %s,
                email_address = %s, job_title = %s, preferred_contact_channel = %s, additional_notes = %s, modified_by = %s
            WHERE id = %s
        """, (
            parent_company_id,
            data['client_name'],
            data['mobile_number'],
            data.get('secondary_mobile_number', '') or None,
            data['email_address'],
            data.get('job_title', ''),
            data.get('preferred_contact_channel', 'Phone'),
            data.get('additional_notes', ''),
            session['username'],
            client_id
        ))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Client updated successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clients/<int:client_id>', methods=['GET'])
@perm('client.view')
def get_client(client_id):
    """API endpoint to get a single client - Admin or client_management role"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # parent_company_id resolves against `company`, the same table the
        # client list and the add/edit validation use. There is no
        # `parent_company` table and never was.
        cur.execute("""
            SELECT c.*, comp.company_name as parent_company_name
            FROM client c
            LEFT JOIN company comp ON c.parent_company_id = comp.id
            WHERE c.id = %s
        """, (client_id,))
        
        client = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        return jsonify(client)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients/delete/<int:client_id>', methods=['DELETE'])
@perm('client.delete')
def delete_client(client_id):
    """API endpoint to delete a client - Admin or client_management role"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Check if client exists
        cur.execute("SELECT id FROM client WHERE id = %s", (client_id,))
        if not cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404
        
        # Delete client
        cur.execute("DELETE FROM client WHERE id = %s", (client_id,))
        conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Client deleted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
# Add this after the client route (around line 1400)
@app.route('/supplier', methods=['GET'])
@perm('supplier.view')
def supplier():
    """Display supplier page - Admin or supplier_management role"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template("supplier.html")

# Update this around line 1570
@app.route('/api/suppliers', methods=['GET'])
@perm('supplier.view')
def get_suppliers():
    """API endpoint to fetch all suppliers - Admin only"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Fetch all suppliers with safe column access
        cur.execute("SELECT * FROM supplier ORDER BY id DESC")
        suppliers_data = cur.fetchall()
        
        # Convert to list of dictionaries for JSON response
        suppliers_list = []
        for supplier in suppliers_data:
            suppliers_list.append({
                'id': supplier.get('id', 0),
                'supplier_name': supplier.get('supplier_name', ''),
                'supplier_type': supplier.get('supplier_type', ''),
                'other_supplier_type': supplier.get('other_supplier_type', ''),
                'company_name': supplier.get('company_name', ''),
                'business_registration_number': supplier.get('business_registration_number', ''),
                'status': supplier.get('status', 'Active'),
                'date_added': supplier['date_added'].strftime('%Y-%m-%d') if supplier.get('date_added') else '',
                'address': supplier.get('address', ''),
                'contact_person_name': supplier.get('contact_person_name', ''),
                'job_title': supplier.get('job_title', ''),
                'primary_phone': supplier.get('primary_phone', ''),
                'secondary_phone': supplier.get('secondary_phone', ''),
                'email_address': supplier.get('email_address', ''),
                'whatsapp_number': supplier.get('whatsapp_number', ''),
                'preferred_contact_method': supplier.get('preferred_contact_method', ''),
                'website': supplier.get('website', ''),
                'additional_notes': supplier.get('additional_notes', ''),
                'added_by': supplier.get('added_by', ''),
                'added_by_name': supplier.get('added_by', ''),
                'added_date': supplier['added_date'].strftime('%Y-%m-%d %H:%M:%S') if supplier.get('added_date') else 'N/A',
                'modified_by': supplier.get('modified_by', ''),
                'modified_by_name': supplier.get('modified_by', ''),
                'modified_date': supplier['modified_date'].strftime('%Y-%m-%d %H:%M:%S') if supplier.get('modified_date') else 'N/A'
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'suppliers': suppliers_list
        })
    except Exception as e:
        print(f"Error in get_suppliers: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Simple endpoint for dropdowns
@app.route('/api/suppliers/simple', methods=['GET'])
@perm('supplier.view')
def get_suppliers_simple():
    """API endpoint to fetch suppliers for dropdowns"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Fetch active suppliers for dropdown
        cur.execute("SELECT id, supplier_name, company_name FROM supplier WHERE status = 'Active' ORDER BY supplier_name")
        suppliers_data = cur.fetchall()
        
        # Convert to list of dictionaries for JSON response
        suppliers_list = []
        for supplier in suppliers_data:
            supplier_name = supplier.get('supplier_name', '')
            company_name = supplier.get('company_name', '')
            
            # Create display name with company in parentheses if available
            if company_name:
                display_name = f"{supplier_name} ({company_name})"
            else:
                display_name = supplier_name
            
            suppliers_list.append({
                'id': supplier.get('id', 0),
                'name': supplier_name,
                'supplier_name': supplier_name,
                'company': company_name,
                'company_name': company_name,
                'display_name': display_name
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'suppliers': suppliers_list
        })
        
    except Exception as e:
        print(f"Error loading suppliers for dropdown: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Add this after the get_suppliers endpoint
@app.route('/api/suppliers/add', methods=['POST'])
@perm('supplier.create')
def add_supplier():
    """API endpoint to add a new supplier - Admin or supplier_management role"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['supplier_name', 'supplier_type', 'status', 'date_added', 
                          'contact_person_name', 'primary_phone', 'email_address', 'preferred_contact_method']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        conn, cur = connection()
        
        # Check if primary phone already exists
        cur.execute("SELECT id FROM supplier WHERE primary_phone = %s", (data['primary_phone'],))
        if cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'Primary phone number already exists'
            }), 400
        
        # Check if email already exists
        cur.execute("SELECT id FROM supplier WHERE email_address = %s", (data['email_address'],))
        if cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'Email address already exists'
            }), 400
        
        # Insert new supplier
        cur.execute("""
            INSERT INTO supplier (supplier_name, supplier_type, other_supplier_type, company_name, 
                                business_registration_number, status, date_added, address, 
                                contact_person_name, job_title, primary_phone, secondary_phone, 
                                email_address, whatsapp_number, preferred_contact_method, 
                                website, additional_notes, added_by, added_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            data['supplier_name'],
            data['supplier_type'],
            data.get('other_supplier_type', ''),
            data.get('company_name', ''),
            data.get('business_registration_number', ''),
            data['status'],
            data['date_added'],
            data.get('address', ''),
            data['contact_person_name'],
            data.get('job_title', ''),
            data['primary_phone'],
            data.get('secondary_phone', ''),
            data['email_address'],
            data.get('whatsapp_number', ''),
            data['preferred_contact_method'],
            data.get('website', ''),
            data.get('notes', ''),
            session['username']
        ))
        
        conn.commit()
        
        # Get the newly inserted supplier ID
        supplier_id = cur.lastrowid
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Supplier added successfully',
            'supplier_id': supplier_id,
            'supplier_name': data['supplier_name']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Add this after the add_supplier endpoint
@app.route('/api/suppliers/edit/<int:supplier_id>', methods=['POST'])
@perm('supplier.edit')
def edit_supplier(supplier_id):
    """API endpoint to edit an existing supplier - Admin or supplier_management role"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401

    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['supplier_name', 'supplier_type', 'status', 'date_added', 
                          'contact_person_name', 'primary_phone', 'email_address', 'preferred_contact_method']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400

        conn, cur = connection()

        # Check current supplier data first
        cur.execute("SELECT primary_phone, email_address FROM supplier WHERE id = %s", (supplier_id,))
        current_supplier = cur.fetchone()
        if not current_supplier:
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Supplier not found'
            }), 404

        # Only check for duplicate primary phone if it's different from current
        if data['primary_phone'] != current_supplier['primary_phone']:
            cur.execute("SELECT id FROM supplier WHERE primary_phone = %s", (data['primary_phone'],))
            duplicate_phone = cur.fetchone()
            if duplicate_phone:
                cur.close()
                conn.close()
                return jsonify({
                    'success': False,
                    'error': 'Primary phone number already exists'
                }), 400

        # Only check for duplicate email if it's different from current
        if data['email_address'] != current_supplier['email_address']:
            cur.execute("SELECT id FROM supplier WHERE email_address = %s", (data['email_address'],))
            duplicate_email = cur.fetchone()
            if duplicate_email:
                cur.close()
                conn.close()
                return jsonify({
                    'success': False,
                    'error': 'Email address already exists'
                }), 400

        # Update supplier details
        cur.execute("""
            UPDATE supplier
            SET supplier_name = %s, supplier_type = %s, other_supplier_type = %s, company_name = %s,
                business_registration_number = %s, status = %s, date_added = %s, address = %s,
                contact_person_name = %s, job_title = %s, primary_phone = %s, secondary_phone = %s,
                email_address = %s, whatsapp_number = %s, preferred_contact_method = %s,
                website = %s, additional_notes = %s, modified_by = %s, modified_date = NOW()
            WHERE id = %s
        """, (
            data['supplier_name'],
            data['supplier_type'],
            data.get('other_supplier_type', ''),
            data.get('company_name', ''),
            data.get('business_registration_number', ''),
            data['status'],
            data['date_added'],
            data.get('address', ''),
            data['contact_person_name'],
            data.get('job_title', ''),
            data['primary_phone'],
            data.get('secondary_phone', ''),
            data['email_address'],
            data.get('whatsapp_number', ''),
            data['preferred_contact_method'],
            data.get('website', ''),
            data.get('notes', ''),
            session['username'],
            supplier_id
        ))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Supplier updated successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Add this after the edit_supplier endpoint
@app.route('/api/suppliers/delete/<int:supplier_id>', methods=['DELETE'])
@perm('supplier.delete')
def delete_supplier(supplier_id):
    """API endpoint to delete a supplier - Admin or supplier_management role"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Check if supplier exists
        cur.execute("SELECT id FROM supplier WHERE id = %s", (supplier_id,))
        if not cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'Supplier not found'
            }), 404
        
        # Delete supplier
        cur.execute("DELETE FROM supplier WHERE id = %s", (supplier_id,))
        conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Supplier deleted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Routes for rendering HTML pages
@app.route('/approvals', methods=['GET'])
@perm('sales_request.approve')
def approvals_page():
    """Render the approvals management page for admins"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('approvals.html')

@app.route('/sales_request', methods=['GET'])
@perm('sales_request.view')
def sales_request():
    """Display sales request page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template("sales_request.html", pricing_mode=False)


@app.route('/sales_request_details/<int:request_id>', methods=['GET'])
@perm('sales_request.view')
def sales_request_details_page(request_id):
    """Privilege-gated read-only details page for a single sales request.
    Data is fetched client-side from /api/sales/requests/<id>.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template("sales_request_details.html", request_id=request_id)


@app.route('/pricing', methods=['GET'])
@perm('sales_item.price')
def pricing_dashboard():
    """Pricing - Operation Dashboard.
    Reuses the sales_request template in read-only mode:
    View + Comments + Repricing only. No add/edit/delete UI.
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template("sales_request.html", pricing_mode=True)

@app.route('/workflow_timeline')
@perm('sales_request.view')
def workflow_timeline():
    """Display workflow timeline page showing status flow of all sales requests"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template("workflow_timeline.html")

@app.route('/api/workflow/requests', methods=['GET'])
@perm('sales_request.view')
def api_workflow_requests():
    """Get all sales requests with summary for timeline view"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    try:
        conn, cur = connection()

        scope_sql, scope_params = scope_clause('sales_request.view', 'sr.owner_user_id')

        cur.execute("""
            SELECT 
                sr.id AS request_id,
                sr.title,
                sr.status,
                sr.approval_status,
                sr.created_at,
                sr.modified_at,
                sr.created_by,
                sr.start_date,
                sr.end_date,
                c.client_name,
                co.company_name,
                COUNT(DISTINCT sri.id) as total_items,
                SUM(CASE WHEN sri.approval_status = 'approved' THEN 1 ELSE 0 END) as approved_items,
                SUM(CASE WHEN sri.approval_status = 'rejected' THEN 1 ELSE 0 END) as rejected_items,
                SUM(CASE WHEN sri.approval_status = 'pending_negotiation' THEN 1 ELSE 0 END) as negotiation_items,
                SUM(CASE WHEN sri.approval_status = 'submitted' THEN 1 ELSE 0 END) as submitted_items,
                SUM(CASE WHEN sri.approval_status = 'pending' THEN 1 ELSE 0 END) as pending_items,
                SUM(CASE WHEN sri.cost_per_item IS NOT NULL THEN 1 ELSE 0 END) as costed_items,
                SUM(CASE WHEN sri.sell_per_item IS NOT NULL THEN 1 ELSE 0 END) as priced_items
            FROM sales_request sr
            LEFT JOIN client c ON sr.client_id = c.id
            LEFT JOIN company co ON sr.company_id = co.id
            LEFT JOIN sales_request_items sri ON sr.id = sri.request_id
            WHERE 1=1 """ + scope_sql + """
            GROUP BY sr.id
            ORDER BY sr.id DESC
        """, scope_params)
        
        requests = cur.fetchall()
        
        # Convert datetime objects to strings
        for req in requests:
            if req.get('created_at'):
                req['created_at'] = req['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            if req.get('modified_at'):
                req['modified_at'] = req['modified_at'].strftime('%Y-%m-%d %H:%M:%S')
            if req.get('start_date'):
                req['start_date'] = req['start_date'].strftime('%Y-%m-%d')
            if req.get('end_date'):
                req['end_date'] = req['end_date'].strftime('%Y-%m-%d')
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'requests': requests})
        
    except Exception as e:
        print(f"Error fetching workflow requests: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/workflow/request/<int:request_id>/timeline', methods=['GET'])
@perm('sales_request.view')
def api_workflow_request_timeline(request_id):
    """Get detailed timeline for a specific sales request"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Get request details
        cur.execute("""
            SELECT sr.id AS request_id, sr.*, c.client_name, co.company_name
            FROM sales_request sr
            LEFT JOIN client c ON sr.client_id = c.id
            LEFT JOIN company co ON sr.company_id = co.id
            WHERE sr.id = %s
        """, (request_id,))
        request_data = cur.fetchone()
        
        if not request_data:
            return jsonify({'success': False, 'error': 'Request not found'}), 404
        
        # Convert datetime objects
        for key in ['created_at', 'modified_at', 'sales_added_date', 'approval_last_updated']:
            if request_data.get(key):
                request_data[key] = request_data[key].strftime('%Y-%m-%d %H:%M:%S')
        for key in ['start_date', 'end_date']:
            if request_data.get(key):
                request_data[key] = request_data[key].strftime('%Y-%m-%d')
        
        # Get request status history
        cur.execute("""
            SELECT * FROM sales_request_status_history
            WHERE request_id = %s
            ORDER BY changed_at ASC
        """, (request_id,))
        status_history = cur.fetchall()
        for h in status_history:
            if h.get('changed_at'):
                h['changed_at'] = h['changed_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        # Get request change log
        cur.execute("""
            SELECT * FROM sales_request_change_log
            WHERE request_id = %s
            ORDER BY action_date ASC
        """, (request_id,))
        change_log = cur.fetchall()
        for c in change_log:
            if c.get('action_date'):
                c['action_date'] = c['action_date'].strftime('%Y-%m-%d %H:%M:%S')
        
        # Get all items for this request
        cur.execute("""
            SELECT 
                sri.*,
                ii.item_code AS inventory_item_code
            FROM sales_request_items sri
            LEFT JOIN inventory_items ii ON ii.sales_request_item_id = sri.id
            WHERE sri.request_id = %s
            ORDER BY sri.id ASC
        """, (request_id,))
        items = cur.fetchall()
        
        # Convert item datetime fields
        for item in items:
            for key in ['created_at', 'submitted_for_approval_date', 'client_approval_date']:
                if item.get(key):
                    item[key] = item[key].strftime('%Y-%m-%d %H:%M:%S')
            # Convert decimal to float
            for key in ['qty', 'cost_per_item', 'sell_per_item', 'total_cost', 'total_sell', 'profit_margin']:
                if item.get(key):
                    item[key] = float(item[key])
        
        # Get item approval logs
        cur.execute("""
            SELECT ical.*, u.name AS action_by_name
            FROM item_client_approval_log ical
            LEFT JOIN user u ON ical.action_by = u.id
            WHERE ical.request_id = %s
            ORDER BY ical.action_date ASC
        """, (request_id,))
        item_approval_logs = cur.fetchall()
        for log in item_approval_logs:
            if log.get('action_date'):
                log['action_date'] = log['action_date'].strftime('%Y-%m-%d %H:%M:%S')
            for key in ['cost_per_item', 'sell_per_item']:
                if log.get(key):
                    log[key] = float(log[key])
        
        # Get item price history
        cur.execute("""
            SELECT * FROM sales_request_item_price_history
            WHERE request_id = %s
            ORDER BY created_at ASC
        """, (request_id,))
        price_history = cur.fetchall()
        for p in price_history:
            if p.get('created_at'):
                p['created_at'] = p['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            for key in ['cost_per_item', 'sell_per_item', 'total_cost', 'total_sell', 'profit_amount', 'profit_margin']:
                if p.get(key):
                    p[key] = float(p[key])
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'request': request_data,
            'status_history': status_history,
            'change_log': change_log,
            'items': items,
            'item_approval_logs': item_approval_logs,
            'price_history': price_history
        })
        
    except Exception as e:
        print(f"Error fetching workflow timeline: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/operation_request', methods=['GET'])
@perm('approved_item.view')
def operation_request():
    """Display operation request page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template("operation_request.html")

# API endpoints for requests
@app.route('/api/requests', methods=['GET'])
@perm('sales_request.view')
def get_requests():
    """API endpoint to fetch all requests"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Fetch all requests with items (using actual table and column names)
        cur.execute("""
            SELECT r.request_id, r.client_name, r.total_sell, r.total_cost, 
                   r.sales_added_date, r.sales_added_by, r.modified_date,
                   COUNT(i.item_id) as item_count,
                   SUM(i.total_quantity) as total_quantity
            FROM request r
            LEFT JOIN items i ON r.request_id = i.request_id
            GROUP BY r.request_id
            ORDER BY r.request_id DESC
        """)
        requests_data = cur.fetchall()
        
        # Convert to list of dictionaries for JSON response
        requests_list = []
        for req in requests_data:
            requests_list.append({
                'id': req.get('request_id', 0),
                'request_number': f"REQ{req.get('request_id', 0):06d}",
                'client_name': req.get('client_name', ''),
                'project_name': req.get('client_name', ''),  # Using client_name as project name for now
                'expected_delivery_date': '',
                'status': 'Pending',  # Default status
                'notes': '',
                'added_by': req.get('sales_added_by', ''),
                'added_date': req['sales_added_date'].strftime('%Y-%m-%d %H:%M:%S') if req.get('sales_added_date') else '',
                'modified_by': '',
                'modified_date': req['modified_date'].strftime('%Y-%m-%d %H:%M:%S') if req.get('modified_date') else '',
                'item_count': req.get('item_count', 0),
                'total_quantity': req.get('total_quantity', 0),
                'total_cost': float(req.get('total_cost', 0)) if req.get('total_cost') else 0,
                'total_selling_price': float(req.get('total_sell', 0)) if req.get('total_sell') else 0
            })
        
        cur.close()
        conn.close()
        
        return jsonify(requests_list)
        
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route('/api/requests/<int:request_id>/items', methods=['GET'])
@perm('sales_request.view')
def get_request_items(request_id):
    """API endpoint to fetch items for a specific request"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Fetch items for the specific request (using actual table and column names)
        cur.execute("SELECT * FROM items WHERE request_id = %s ORDER BY item_id", (request_id,))
        items_data = cur.fetchall()
        
        # Convert to list of dictionaries for JSON response
        items_list = []
        for item in items_data:
            items_list.append({
                'id': item.get('item_id', 0),
                'request_id': item.get('request_id', 0),
                'item_name': item.get('item_name', ''),
                'item_description': item.get('item_comment', ''),
                'quantity': item.get('total_quantity', 0),
                'unit_cost': float(item.get('total_cost', 0)) if item.get('total_cost') else 0,
                'selling_price': float(item.get('total_sell', 0)) if item.get('total_sell') else 0,
                'supplier_id': 0,  # Not in current schema
                'notes': item.get('item_comment', ''),
                'added_by': item.get('sales_added_by', ''),
                'added_date': item['sales_added_date'].strftime('%Y-%m-%d %H:%M:%S') if item.get('sales_added_date') else '',
                'modified_by': item.get('sales_modified_by', ''),
                'modified_date': item['sales_modified_date'].strftime('%Y-%m-%d %H:%M:%S') if item.get('sales_modified_date') else ''
            })
        
        cur.close()
        conn.close()
        
        return jsonify(items_list)
        
    except Exception as e:
        return jsonify(error=str(e)), 500

# Sales and Operations API endpoints (with /api/ prefix)
@app.route('/api/sales/requests', methods=['GET'])
@perm('sales_request.view')
def get_sales_requests():
    """API endpoint to fetch all sales requests for DataTable - Enhanced for revamp"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Check if new sales_request table exists
        cur.execute("""
            SELECT COUNT(*) as table_exists
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = 'sales_request'
        """)
        table_check = cur.fetchone()
        
        requests_list = []
        
        if table_check and table_check['table_exists'] > 0:
            # Check if company_id column exists in sales_request table
            cur.execute("""
                SELECT COUNT(*) as column_exists
                FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                AND table_name = 'sales_request' 
                AND column_name = 'company_id'
            """)
            company_id_exists = cur.fetchone()['column_exists'] > 0
            
            # Row-level scope: own / team / department / all.
            scope_sql, scope_params = scope_clause('sales_request.view', 'sr.owner_user_id')
            
            if company_id_exists:
                # Use new schema with company support - includes approval tracking
                # Item states are MUTUALLY EXCLUSIVE following this hierarchy:
                # 1. not_costed: cost_per_item IS NULL
                # 2. not_priced: cost set but sell_per_item IS NULL  
                # 3. pending: both prices set AND approval_status = 'pending'
                # 4. pending_negotiation: approval_status = 'pending_negotiation'
                # 5. approved: approval_status = 'approved'
                # 6. rejected: approval_status = 'rejected'
                cur.execute("""
                    SELECT sr.id, sr.company_id, sr.client_id, sr.request_type, sr.title, 
                           sr.status, sr.priority, sr.start_date, sr.end_date, 
                           sr.budget_total, sr.currency, sr.items_count, sr.total_cost, 
                           sr.total_sell, sr.client_approval_stage, sr.created_by, sr.created_at, sr.modified_at,
                           c.client_name, comp.company_name,
                           COUNT(CASE WHEN i.cost_per_item IS NOT NULL AND i.cost_per_item > 0 
                                          AND (i.approval_status != 'pending_negotiation' OR i.approval_status IS NULL) THEN 1 END) as costed_items_count,
                           COUNT(CASE WHEN i.cost_per_item IS NULL THEN 1 END) as approval_stats_not_costed,
                           COUNT(CASE WHEN i.cost_per_item IS NOT NULL AND i.sell_per_item IS NULL THEN 1 END) as approval_stats_not_priced,
                           COUNT(CASE WHEN i.cost_per_item IS NOT NULL AND i.sell_per_item IS NOT NULL 
                                          AND (i.approval_status = 'pending' OR i.approval_status IS NULL) THEN 1 END) as approval_stats_pending,
                           COUNT(CASE WHEN i.approval_status = 'pending_negotiation' AND (i.negotiation_status IS NULL OR i.negotiation_status = 'none' OR i.negotiation_status = 'pending_negotiation') THEN 1 END) as approval_stats_negotiation,
                           COUNT(CASE WHEN i.approval_status = 'pending_negotiation' AND i.negotiation_status = 'negotiated' THEN 1 END) as approval_stats_repricing,
                           COUNT(CASE WHEN i.approval_status = 'approved' THEN 1 END) as approval_stats_approved,
                           COUNT(CASE WHEN i.approval_status = 'rejected' THEN 1 END) as approval_stats_rejected,
                           COALESCE((SELECT COUNT(*) FROM sales_request_comments src WHERE src.request_id = sr.id AND src.is_deleted = 0), 0) as comment_count
                    FROM sales_request sr
                    LEFT JOIN client c ON sr.client_id = c.id
                    LEFT JOIN company comp ON sr.company_id = comp.id
                    LEFT JOIN sales_request_items i ON sr.id = i.request_id
                    WHERE 1=1 """ + scope_sql + """
                    GROUP BY sr.id, sr.company_id, sr.client_id, sr.request_type, sr.title, 
                             sr.status, sr.priority, sr.start_date, sr.end_date, 
                             sr.budget_total, sr.currency, sr.items_count, sr.total_cost, 
                             sr.total_sell, sr.client_approval_stage, sr.created_by, sr.created_at, sr.modified_at,
                             c.client_name, comp.company_name
                    ORDER BY sr.id DESC
                """, scope_params)
            else:
                # Use new schema without company support (fallback) - includes approval tracking
                # Item states are MUTUALLY EXCLUSIVE (same as above)
                cur.execute("""
                    SELECT sr.id, sr.client_id, sr.request_type, sr.title, 
                           sr.status, sr.priority, sr.start_date, sr.end_date, 
                           sr.budget_total, sr.currency, sr.items_count, sr.total_cost, 
                           sr.total_sell, sr.client_approval_stage, sr.created_by, sr.created_at, sr.modified_at,
                           c.client_name, c.parent_company_id,
                           comp.company_name,
                           COUNT(CASE WHEN i.cost_per_item IS NOT NULL AND i.cost_per_item > 0 
                                          AND (i.approval_status != 'pending_negotiation' OR i.approval_status IS NULL) THEN 1 END) as costed_items_count,
                           COUNT(CASE WHEN i.cost_per_item IS NULL THEN 1 END) as approval_stats_not_costed,
                           COUNT(CASE WHEN i.cost_per_item IS NOT NULL AND i.sell_per_item IS NULL THEN 1 END) as approval_stats_not_priced,
                           COUNT(CASE WHEN i.cost_per_item IS NOT NULL AND i.sell_per_item IS NOT NULL 
                                          AND (i.approval_status = 'pending' OR i.approval_status IS NULL) THEN 1 END) as approval_stats_pending,
                           COUNT(CASE WHEN i.approval_status = 'pending_negotiation' AND (i.negotiation_status IS NULL OR i.negotiation_status = 'pending_negotiation') THEN 1 END) as approval_stats_negotiation,
                           COUNT(CASE WHEN i.approval_status = 'pending_negotiation' AND i.negotiation_status = 'negotiated' THEN 1 END) as approval_stats_repricing,
                           COUNT(CASE WHEN i.approval_status = 'approved' THEN 1 END) as approval_stats_approved,
                           COUNT(CASE WHEN i.approval_status = 'rejected' THEN 1 END) as approval_stats_rejected
                    FROM sales_request sr
                    LEFT JOIN client c ON sr.client_id = c.id
                    LEFT JOIN company comp ON c.parent_company_id = comp.id
                    LEFT JOIN sales_request_items i ON sr.id = i.request_id
                    WHERE 1=1 """ + scope_sql + """
                    GROUP BY sr.id, sr.client_id, sr.request_type, sr.title, 
                             sr.status, sr.priority, sr.start_date, sr.end_date, 
                             sr.budget_total, sr.currency, sr.items_count, sr.total_cost, 
                             sr.total_sell, sr.client_approval_stage, sr.created_by, sr.created_at, sr.modified_at,
                             c.client_name, c.parent_company_id, comp.company_name
                    ORDER BY sr.id DESC
                """, scope_params)
            new_requests = cur.fetchall()
            
            for req in new_requests:
                # Calculate status display
                status_display = req.get('status', 'submitted').title()
                if req.get('priority') == 'urgent':
                    status_display = f"🔴 {status_display}"
                elif req.get('priority') == 'high':
                    status_display = f"🟠 {status_display}"
                
                requests_list.append({
                    'request_id': req.get('id', 0),
                    'company_id': req.get('company_id') if company_id_exists else req.get('parent_company_id'),
                    'company_name': req.get('company_name', ''),
                    'client_id': req.get('client_id'),
                    'client_name': req.get('client_name', ''),
                    'status': status_display,
                    'items_count': req.get('items_count', 0),
                    'costed_items_count': req.get('costed_items_count', 0),
                    'total_cost': float(req.get('total_cost', 0)) if req.get('total_cost') else 0,
                    'total_sell': float(req.get('total_sell', 0)) if req.get('total_sell') else 0,
                    'client_approval_stage': req.get('client_approval_stage', 'not_submitted'),
                    'comment_count': req.get('comment_count', 0),
                    'approval_stats': {
                        'not_costed': req.get('approval_stats_not_costed', 0),
                        'not_priced': req.get('approval_stats_not_priced', 0),
                        'pending': req.get('approval_stats_pending', 0),
                        'negotiation': req.get('approval_stats_negotiation', 0),
                        'repricing': req.get('approval_stats_repricing', 0),
                        'approved': req.get('approval_stats_approved', 0),
                        'rejected': req.get('approval_stats_rejected', 0)
                    },
                    'sales_added_date': req['created_at'].strftime('%Y-%m-%d %H:%M:%S') if req.get('created_at') else '',
                    'sales_added_by': req.get('created_by', ''),
                    'request_type': req.get('request_type', 'General'),
                    'title': req.get('title', ''),
                    'priority': req.get('priority', 'normal'),
                    'start_date': req['start_date'].strftime('%Y-%m-%d') if req.get('start_date') else '',
                    'end_date': req['end_date'].strftime('%Y-%m-%d') if req.get('end_date') else ''
                })
        
        # Also fetch from legacy table for backward compatibility
        try:
            cur.execute("""
                SELECT r.request_id, r.client_name, r.total_sell, r.total_cost, 
                       r.sales_added_date, r.sales_added_by, r.modified_date,
                       COUNT(i.item_id) as item_count,
                       SUM(i.total_quantity) as total_quantity
                FROM request r
                LEFT JOIN items i ON r.request_id = i.request_id
                GROUP BY r.request_id
                ORDER BY r.request_id DESC
            """)
            legacy_requests = cur.fetchall()
            
            for req in legacy_requests:
                # Check if this request already exists in new format
                existing = next((r for r in requests_list if r['request_id'] == req.get('request_id', 0)), None)
                if not existing:
                    requests_list.append({
                        'request_id': req.get('request_id', 0),
                        'client_name': req.get('client_name', ''),
                        'status': 'Legacy Request',
                        'items_count': req.get('item_count', 0),
                        'total_cost': float(req.get('total_cost', 0)) if req.get('total_cost') else 0,
                        'total_sell': float(req.get('total_sell', 0)) if req.get('total_sell') else 0,
                        'sales_added_date': req['sales_added_date'].strftime('%Y-%m-%d %H:%M:%S') if req.get('sales_added_date') else '',
                        'sales_added_by': req.get('sales_added_by', ''),
                        'request_type': 'General',
                        'title': f'Legacy Request #{req.get("request_id", 0)}',
                        'priority': 'normal'
                    })
        except Exception as e:
            print(f"DEBUG: Legacy table query failed: {e}")
        
        # Sort by request_id descending
        requests_list.sort(key=lambda x: x['request_id'], reverse=True)
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'requests': requests_list
        })
        
    except Exception as e:
        print(f"DEBUG: Error in get_sales_requests: {e}")
        import traceback
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/operations/requests', methods=['GET'])
@perm('sales_request.view')
def get_operations_requests():
    """API endpoint to fetch all operations requests for DataTable"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Check if company_id column exists
        cur.execute("""
            SELECT COUNT(*) as column_exists
            FROM information_schema.columns 
            WHERE table_schema = DATABASE() 
            AND table_name = 'sales_request' 
            AND column_name = 'company_id'
        """)
        company_id_exists = cur.fetchone()['column_exists'] > 0
        
        # Fetch all requests with items and cost status (using correct table names)
        if company_id_exists:
            cur.execute("""
                SELECT sr.id as request_id, 
                       c.client_name, 
                       comp.company_name,
                       sr.title,
                       sr.request_type,
                       sr.total_sell, sr.total_cost, 
                       sr.status,
                       sr.created_at as sales_added_date, 
                       sr.created_by as sales_added_by, 
                       sr.modified_at as modified_date,
                       sr.items_count as item_count,
                       SUM(i.qty) as total_quantity,
                       COUNT(CASE WHEN i.cost_per_item IS NOT NULL AND i.cost_per_item > 0 
                                  AND NOT (i.approval_status = 'pending_negotiation' 
                                           AND (i.negotiation_status IS NULL OR i.negotiation_status = 'none' OR i.negotiation_status = 'pending_negotiation'))
                             THEN 1 END) as costed_items_count,
                       COUNT(CASE WHEN i.approval_status = 'pending_negotiation' AND (i.negotiation_status IS NULL OR i.negotiation_status = 'none' OR i.negotiation_status = 'pending_negotiation') THEN 1 END) as renegotiation_items_count,
                       COUNT(CASE WHEN (i.cost_per_item IS NULL OR i.cost_per_item = 0) THEN 1 END) as pending_items_count
                FROM sales_request sr
                LEFT JOIN client c ON sr.client_id = c.id
                LEFT JOIN company comp ON sr.company_id = comp.id
                LEFT JOIN sales_request_items i ON sr.id = i.request_id
                GROUP BY sr.id, sr.items_count
                ORDER BY sr.id DESC
            """)
        else:
            cur.execute("""
                SELECT sr.id as request_id, 
                       c.client_name,
                       comp.company_name,
                       sr.title,
                       sr.request_type,
                       sr.total_sell, sr.total_cost, 
                       sr.status,
                       sr.created_at as sales_added_date, 
                       sr.created_by as sales_added_by, 
                       sr.modified_at as modified_date,
                       sr.items_count as item_count,
                       SUM(i.qty) as total_quantity,
                       COUNT(CASE WHEN i.cost_per_item IS NOT NULL AND i.cost_per_item > 0 
                                  AND NOT (i.approval_status = 'pending_negotiation' 
                                           AND (i.negotiation_status IS NULL OR i.negotiation_status = 'none' OR i.negotiation_status = 'pending_negotiation'))
                             THEN 1 END) as costed_items_count,
                       COUNT(CASE WHEN i.approval_status = 'pending_negotiation' AND (i.negotiation_status IS NULL OR i.negotiation_status = 'none' OR i.negotiation_status = 'pending_negotiation') THEN 1 END) as renegotiation_items_count,
                       COUNT(CASE WHEN (i.cost_per_item IS NULL OR i.cost_per_item = 0) THEN 1 END) as pending_items_count
                FROM sales_request sr
                LEFT JOIN client c ON sr.client_id = c.id
                LEFT JOIN company comp ON c.parent_company_id = comp.id
                LEFT JOIN sales_request_items i ON sr.id = i.request_id
                GROUP BY sr.id, sr.items_count
                ORDER BY sr.id DESC
            """)
        requests_data = cur.fetchall()
        
        print(f"DEBUG: Found {len(requests_data)} requests")
        
        # Convert to list of dictionaries for JSON response
        requests_list = []
        for req in requests_data:
            # Determine status based on cost completion
            total_items = req.get('item_count', 0)
            costed_items = req.get('costed_items_count', 0)
            renegotiation_items = req.get('renegotiation_items_count', 0)
            pending_items = req.get('pending_items_count', 0)
            
            print(f"DEBUG: Request {req.get('request_id')} - Total: {total_items}, Costed: {costed_items}, Renegotiation: {renegotiation_items}, Pending: {pending_items}")
            
            if total_items == 0:
                status = 'No Items'
            elif costed_items == total_items:
                status = 'Completed'
            else:
                # Build detailed status
                status_parts = []
                if costed_items > 0:
                    status_parts.append(f'{costed_items}/{total_items} Costed')
                if renegotiation_items > 0:
                    status_parts.append(f'{renegotiation_items} Re-costing Needed')
                if pending_items > 0:
                    status_parts.append(f'{pending_items} Pending')
                status = ', '.join(status_parts) if status_parts else 'Pending'
            
            requests_list.append({
                'request_id': req.get('request_id', 0),
                'client_name': req.get('client_name', ''),
                'company_name': req.get('company_name', ''),
                'title': req.get('title', ''),
                'request_type': req.get('request_type', ''),
                'status': status,
                'items_count': total_items,
                'costed_items_count': costed_items,
                'renegotiation_items_count': renegotiation_items,
                'pending_items_count': pending_items,
                'total_cost': float(req.get('total_cost', 0)) if req.get('total_cost') else 0,
                'total_sell': float(req.get('total_sell', 0)) if req.get('total_sell') else 0,
                'sales_added_date': req['sales_added_date'].strftime('%Y-%m-%d %H:%M:%S') if req.get('sales_added_date') else '',
                'sales_added_by': req.get('sales_added_by', '')
            })
        
        cur.close()
        conn.close()
        
        print(f"DEBUG: Returning {len(requests_list)} requests")
        
        return jsonify({
            'success': True,
            'requests': requests_list
        })
        
    except Exception as e:
        print(f"DEBUG: Error in get_operations_requests: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales/requests/<int:request_id>', methods=['GET'])
@perm('sales_request.view')
def get_single_sales_request(request_id):
    """API endpoint to fetch a single sales request with items - Enhanced with duration"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Check if company_id column exists
        cur.execute("""
            SELECT COUNT(*) as column_exists
            FROM information_schema.columns 
            WHERE table_schema = DATABASE() 
            AND table_name = 'sales_request' 
            AND column_name = 'company_id'
        """)
        company_id_exists = cur.fetchone()['column_exists'] > 0
        
        # Query with or without company_id
        if company_id_exists:
            cur.execute("""
                SELECT sr.*, c.client_name, comp.company_name
                FROM sales_request sr
                LEFT JOIN client c ON sr.client_id = c.id
                LEFT JOIN company comp ON sr.company_id = comp.id
                WHERE sr.id = %s
            """, (request_id,))
        else:
            cur.execute("""
                SELECT sr.*, c.client_name, c.parent_company_id, comp.company_name
                FROM sales_request sr
                LEFT JOIN client c ON sr.client_id = c.id
                LEFT JOIN company comp ON c.parent_company_id = comp.id
                WHERE sr.id = %s
            """, (request_id,))
        
        request_data = cur.fetchone()
        
        if not request_data:
            return jsonify({
                'success': False,
                'error': 'Request not found'
            }), 404

        # Row-level scope: a caller with own or team scope may not open
        # somebody else's request just by knowing its id.
        assert_scope('sales_request.view', request_data.get('owner_user_id'))

        # Calculate duration
        duration_days = 0
        if request_data.get('start_date') and request_data.get('end_date'):
            duration_days = calculate_duration_days(
                request_data['start_date'],
                request_data['end_date']
            )
        elif request_data.get('start_date'):
            # If only start date, duration is 1 day
            duration_days = 1
        
        # Parse request types
        request_type_raw = request_data.get('request_type', '')
        request_types_list = [rt.strip() for rt in request_type_raw.split(',')] if request_type_raw else []
        
        # Parse request_data JSON
        request_data_json = {}
        if request_data.get('request_data'):
            try:
                if isinstance(request_data['request_data'], str):
                    request_data_json = json.loads(request_data['request_data'])
                else:
                    request_data_json = request_data['request_data']
            except:
                request_data_json = {}
        
        # NEW: Get template instances from the new table
        template_instances = []
        try:
            cur.execute("""
                SELECT id, template_id, request_type, instance_order, template_data, created_at
                FROM sales_request_template_instances 
                WHERE request_id = %s 
                ORDER BY instance_order
            """, (request_id,))
            instances_data = cur.fetchall()
            
            for inst in instances_data:
                template_data = {}
                if inst.get('template_data'):
                    try:
                        if isinstance(inst['template_data'], str):
                            template_data = json.loads(inst['template_data'])
                        else:
                            template_data = inst['template_data']
                    except:
                        template_data = {}
                
                template_instances.append({
                    'id': inst.get('id'),
                    'template_id': inst.get('template_id'),
                    'request_type': inst.get('request_type'),
                    'instance_id': f"{inst.get('template_id')}_{inst.get('request_type').replace(' ', '_')}",
                    'order': inst.get('instance_order'),
                    'fields': template_data
                })
            
            print(f"DEBUG: Retrieved {len(template_instances)} template instances for request {request_id}")
        # A scope refusal is a 403, not a server error.
        except HTTPException:
            raise
        except Exception as inst_error:
            # Table might not exist yet - that's okay
            print(f"DEBUG: Could not retrieve template instances: {inst_error}")
            template_instances = []
        
        # Get items - check if request_type column exists
        cur.execute("""
            SELECT COUNT(*) as column_exists
            FROM information_schema.columns 
            WHERE table_schema = DATABASE() 
            AND table_name = 'sales_request_items' 
            AND column_name = 'request_type'
        """)
        request_type_col_exists = cur.fetchone()['column_exists'] > 0
        
        if request_type_col_exists:
            cur.execute("""
                SELECT * FROM sales_request_items 
                WHERE request_id = %s 
                ORDER BY request_type, id
            """, (request_id,))
        else:
            cur.execute("""
                SELECT * FROM sales_request_items 
                WHERE request_id = %s 
                ORDER BY id
            """, (request_id,))
        
        items_data = cur.fetchall()
        
        # Build response
        request_info = {
            'request_id': request_data.get('id', request_data.get('request_id', 0)),
            'company_id': request_data.get('company_id') if company_id_exists else request_data.get('parent_company_id'),
            'company_name': request_data.get('company_name', ''),
            'client_id': request_data.get('client_id'),
            'client_name': request_data.get('client_name', ''),
            'title': request_data.get('title', ''),
            'description': request_data.get('description', ''),
            'priority': request_data.get('priority', 'normal'),
            'start_date': request_data.get('start_date').strftime('%Y-%m-%d') if request_data.get('start_date') else '',
            'end_date': request_data.get('end_date').strftime('%Y-%m-%d') if request_data.get('end_date') else '',
            'duration_days': duration_days,
            'duration': f"{duration_days} day{'s' if duration_days != 1 else ''}" if duration_days > 0 else '',
            'request_type': request_type_raw,
            'request_types': request_types_list,
            'template_code': request_data.get('template_code', ''),
            'request_data': request_data_json,
            'template_fields': request_data_json.get('template_fields', {}),
            'template_instances': template_instances,  # NEW: Include template instances
            'total_cost': float(request_data.get('total_cost', 0)) if request_data.get('total_cost') else 0,
            'total_sell': float(request_data.get('total_sell', 0)) if request_data.get('total_sell') else 0,
            'status': request_data.get('status', 'Pending'),
            'sales_added_date': request_data.get('created_at', request_data.get('sales_added_date', '')).strftime('%Y-%m-%d %H:%M:%S') if request_data.get('created_at') or request_data.get('sales_added_date') else '',
            'sales_added_by': request_data.get('created_by', request_data.get('sales_added_by', '')),
            'last_modified': request_data.get('modified_at', request_data.get('modified_date', '')).strftime('%Y-%m-%d %H:%M:%S') if request_data.get('modified_at') or request_data.get('modified_date') else 'Not modified',
            'items': []
        }
        
        # Process items and group by request_type
        items_by_request_type = {}  # Dictionary to group items by request type
        
        for item in items_data:
            # Parse attributes JSON to extract measurements
            attributes = {}
            if item.get('attributes'):
                try:
                    if isinstance(item['attributes'], str):
                        attributes = json.loads(item['attributes'])
                    else:
                        attributes = item['attributes']
                except:
                    attributes = {}
            
            item_dict = {
                'id': item.get('id', 0),
                'name': item.get('name', ''),
                'item_name': item.get('name', ''),
                'qty': float(item.get('qty', 1)),
                'quantity': float(item.get('qty', 1)),
                'total_quantity': float(item.get('qty', 1)),
                'description': item.get('description', ''),
                'comment': item.get('description', ''),
                'item_comment': item.get('description', ''),
                'unit': item.get('unit', 'pcs'),
                'sell_type': item.get('sell_type', 'rent'),
                'rental_days': int(item.get('rental_days', 1)) if item.get('rental_days') else 1,
                'dimension_calc': item.get('dimension_calc', ''),
                'include_days_in_calc': bool(item.get('include_days_in_calc', 1)),
                'include_qty_in_calc': bool(item.get('include_qty_in_calc', 1)),
                'cost_per_item': float(item.get('cost_per_item', 0)) if item.get('cost_per_item') else None,
                'sell_per_item': float(item.get('sell_per_item', 0)) if item.get('sell_per_item') else None,
                'total_cost': float(item.get('total_cost', 0)) if item.get('total_cost') else None,
                'total_sell': float(item.get('total_sell', 0)) if item.get('total_sell') else None,
                'approval_status': item.get('approval_status'),
                'negotiation_status': item.get('negotiation_status'),
                'negotiation_reason': item.get('negotiation_reason'),
                'negotiation_count': item.get('negotiation_count', 0),
                'client_feedback': item.get('client_feedback', '')
            }

            cur.execute("""
                SELECT id, status, client_expected_price, client_reason,
                       destination_team, new_cost_price, new_selling_price
                FROM negotiation_requests
                WHERE item_id = %s
                  AND status IN ('pending_sales_head', 'pending_pricing', 'pending_costing')
                ORDER BY id DESC
                LIMIT 1
            """, (item.get('id'),))
            active_negotiation = cur.fetchone()
            if active_negotiation:
                item_dict['active_negotiation'] = {
                    'id': active_negotiation['id'],
                    'status': active_negotiation['status'],
                    'client_expected_price': float(active_negotiation['client_expected_price']) if active_negotiation.get('client_expected_price') is not None else None,
                    'client_reason': active_negotiation.get('client_reason'),
                    'destination_team': active_negotiation.get('destination_team'),
                    'new_cost_price': float(active_negotiation['new_cost_price']) if active_negotiation.get('new_cost_price') is not None else None,
                    'new_selling_price': float(active_negotiation['new_selling_price']) if active_negotiation.get('new_selling_price') is not None else None
                }
            
            # Add measurements from attributes
            if attributes.get('width'):
                item_dict['width'] = float(attributes['width'])
            if attributes.get('height'):
                item_dict['height'] = float(attributes['height'])
            if attributes.get('depth'):
                item_dict['depth'] = float(attributes['depth'])
            
            # Get images for this item
            cur.execute("""
                SELECT id, image_path, image_name, image_size, display_order
                FROM sales_request_item_images
                WHERE item_id = %s
                ORDER BY display_order
            """, (item.get('id'),))
            images = cur.fetchall()
            
            item_dict['images'] = []
            for img in images:
                item_dict['images'].append({
                    'id': img['id'],
                    'path': img['image_path'],
                    'name': img['image_name'],
                    'size': img['image_size'],
                    'order': img['display_order']
                })
            
            # Add image_url for backward compatibility (first image or from attributes)
            if item_dict['images']:
                item_dict['image_url'] = item_dict['images'][0]['path']
            elif attributes.get('image_url'):
                item_dict['image_url'] = attributes['image_url']
            
            # Get attachments from item_images table (includes both images and PDFs)
            cur.execute("""
                SELECT id, image_path, image_type, file_size
                FROM item_images
                WHERE item_id = %s
                ORDER BY uploaded_at
            """, (item.get('id'),))
            attachments_data = cur.fetchall()
            
            item_dict['attachments'] = []
            for att in attachments_data:
                file_path = att['image_path']
                file_ext = att['image_type'].lower()
                
                # Determine MIME type
                if file_ext == 'pdf':
                    mime_type = 'application/pdf'
                elif file_ext in ['jpg', 'jpeg']:
                    mime_type = 'image/jpeg'
                elif file_ext == 'png':
                    mime_type = 'image/png'
                elif file_ext == 'gif':
                    mime_type = 'image/gif'
                else:
                    mime_type = f'image/{file_ext}'
                
                # Extract filename from path
                original_name = os.path.basename(file_path)
                
                item_dict['attachments'].append({
                    'id': att['id'],
                    'file_url': '/' + file_path,
                    'original_name': original_name,
                    'file_type': mime_type,
                    'file_size': att['file_size']
                })
            
            # NEW: Group items by request_type if column exists
            if request_type_col_exists and item.get('request_type'):
                item_request_type = item.get('request_type')
                item_dict['request_type'] = item_request_type
                
                if item_request_type not in items_by_request_type:
                    items_by_request_type[item_request_type] = []
                items_by_request_type[item_request_type].append(item_dict)
            
            # Always add to main items array for backward compatibility
            request_info['items'].append(item_dict)
        
        # NEW: Add items to their respective template instances
        for instance in template_instances:
            instance_request_type = instance.get('request_type')
            if instance_request_type in items_by_request_type:
                instance['items'] = items_by_request_type[instance_request_type]
                print(f"DEBUG: Added {len(instance['items'])} items to instance of type '{instance_request_type}'")
            else:
                instance['items'] = []
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'request': request_info
        })
        
    # A scope refusal is a 403, not a server error.
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Error in get_single_sales_request: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/operations/requests/<int:request_id>', methods=['GET'])
@perm('sales_request.view')
def get_single_operations_request(request_id):
    """API endpoint to fetch a single operations request with items"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Check if company_id column exists
        cur.execute("""
            SELECT COUNT(*) as column_exists
            FROM information_schema.columns 
            WHERE table_schema = DATABASE() 
            AND table_name = 'sales_request' 
            AND column_name = 'company_id'
        """)
        company_id_exists = cur.fetchone()['column_exists'] > 0
        
        # Get request details (using correct table names)
        if company_id_exists:
            cur.execute("""
                SELECT sr.id as request_id, 
                       c.client_name,
                       comp.company_name,
                       sr.title,
                       sr.request_type,
                       sr.total_sell, sr.total_cost, 
                       sr.status,
                       sr.created_at as sales_added_date, 
                       sr.created_by as sales_added_by, 
                       sr.modified_at as modified_date
                FROM sales_request sr
                LEFT JOIN client c ON sr.client_id = c.id
                LEFT JOIN company comp ON sr.company_id = comp.id
                WHERE sr.id = %s
            """, (request_id,))
        else:
            cur.execute("""
                SELECT sr.id as request_id, 
                       c.client_name,
                       comp.company_name,
                       sr.title,
                       sr.request_type,
                       sr.total_sell, sr.total_cost, 
                       sr.status,
                       sr.created_at as sales_added_date, 
                       sr.created_by as sales_added_by, 
                       sr.modified_at as modified_date
                FROM sales_request sr
                LEFT JOIN client c ON sr.client_id = c.id
                LEFT JOIN company comp ON c.parent_company_id = comp.id
                WHERE sr.id = %s
            """, (request_id,))
        request_data = cur.fetchone()
        
        if not request_data:
            return jsonify({
                'success': False,
                'error': 'Request not found'
            }), 404
        
        # Get items for this request (using correct table names)
        cur.execute("""
            SELECT id, name, qty as quantity, description as item_comment, 
                   cost_per_item, sell_per_item, total_cost, total_sell, unit, attributes,
                   approval_status, negotiation_status, negotiation_reason, negotiation_count,
                   sell_type, rental_days, dimension_calc, include_days_in_calc, include_qty_in_calc
            FROM sales_request_items 
            WHERE request_id = %s 
            ORDER BY id
        """, (request_id,))
        items_data = cur.fetchall()
        
        print(f"DEBUG: Found {len(items_data)} items for request {request_id}")
        
        # Calculate status based on costed items
        total_items = len(items_data)
        costed_items = len([item for item in items_data if item.get('cost_per_item') and item.get('cost_per_item') > 0])
        
        if total_items == 0:
            status = 'No Items'
        elif costed_items == 0:
            status = 'Pending'
        elif costed_items == total_items:
            status = 'Completed'
        else:
            status = 'Pending'  # Partially costed - still pending
        
        # Convert to response format (matching frontend expectations)
        request_info = {
            'request_id': request_data.get('request_id', 0),
            'client_name': request_data.get('client_name', ''),
            'company_name': request_data.get('company_name', ''),
            'title': request_data.get('title', ''),
            'request_type': request_data.get('request_type', ''),
            'status': status,
            'total_items': total_items,
            'costed_items': costed_items,
            'total_cost': float(request_data.get('total_cost', 0)) if request_data.get('total_cost') else 0,
            'total_sell': float(request_data.get('total_sell', 0)) if request_data.get('total_sell') else 0,
            'sales_added_date': request_data['sales_added_date'].strftime('%Y-%m-%d %H:%M:%S') if request_data.get('sales_added_date') else '',
            'sales_added_by': request_data.get('sales_added_by', ''),
            'items': []
        }
        
        for item in items_data:
            unit_cost = float(item.get('cost_per_item', 0)) if item.get('cost_per_item') else 0
            has_cost = unit_cost > 0
            
            # Parse attributes JSON to extract measurements (dimensions)
            attributes = {}
            if item.get('attributes'):
                try:
                    if isinstance(item['attributes'], str):
                        attributes = json.loads(item['attributes'])
                    else:
                        attributes = item['attributes']
                except:
                    attributes = {}
            
            item_dict = {
                'id': item.get('id', 0),
                'item_name': item.get('name', ''),
                'total_quantity': float(item.get('quantity', 0)) if item.get('quantity') else 0,
                'unit': item.get('unit', 'pcs'),
                'item_comment': item.get('item_comment', ''),
                'unit_cost': unit_cost,
                'selling_price': float(item.get('sell_per_item', 0)) if item.get('sell_per_item') else 0,
                'total_cost': float(item.get('total_cost', 0)) if item.get('total_cost') else 0,
                'total_sell': float(item.get('total_sell', 0)) if item.get('total_sell') else 0,
                'has_cost': has_cost,
                'cost_status': 'Costed' if has_cost else 'Pending',
                'approval_status': item.get('approval_status'),
                'negotiation_status': item.get('negotiation_status'),
                'negotiation_reason': item.get('negotiation_reason'),
                'negotiation_count': item.get('negotiation_count', 0)
            }
            
            # Add dimensions from attributes
            if attributes.get('width'):
                item_dict['width'] = float(attributes['width'])
            if attributes.get('height'):
                item_dict['height'] = float(attributes['height'])
            if attributes.get('depth'):
                item_dict['depth'] = float(attributes['depth'])
            
            # Add new fields: sell_type, rental_days, dimension_calc, include_days_in_calc, include_qty_in_calc
            item_dict['sell_type'] = item.get('sell_type', 'rent')
            item_dict['rental_days'] = int(item.get('rental_days', 1)) if item.get('rental_days') else 1
            item_dict['dimension_calc'] = item.get('dimension_calc', '')
            item_dict['include_days_in_calc'] = bool(item.get('include_days_in_calc', 1))
            item_dict['include_qty_in_calc'] = bool(item.get('include_qty_in_calc', 1))
            
            # Get attachments for this item from item_images table
            cur.execute("""
                SELECT id, image_path, image_type, file_size
                FROM item_images
                WHERE item_id = %s
                ORDER BY uploaded_at
            """, (item.get('id'),))
            attachments = cur.fetchall()
            
            item_dict['attachments'] = []
            item_dict['image_url'] = None
            
            for att in attachments:
                file_path = att['image_path']
                file_ext = att['image_type'].lower()
                
                # Determine MIME type
                if file_ext == 'pdf':
                    mime_type = 'application/pdf'
                elif file_ext in ['jpg', 'jpeg']:
                    mime_type = 'image/jpeg'
                elif file_ext == 'png':
                    mime_type = 'image/png'
                elif file_ext == 'gif':
                    mime_type = 'image/gif'
                else:
                    mime_type = f'image/{file_ext}'
                
                # Extract filename from path
                original_name = os.path.basename(file_path)
                
                # Set first image as image_url for backward compatibility
                if not item_dict['image_url'] and file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
                    item_dict['image_url'] = '/' + file_path
                
                item_dict['attachments'].append({
                    'id': att['id'],
                    'file_url': '/' + file_path,
                    'original_name': original_name,
                    'file_type': mime_type,
                    'file_size': att['file_size']
                })
            
            request_info['items'].append(item_dict)
        
        cur.close()
        conn.close()
        
        print(f"DEBUG: Returning request info with {len(request_info['items'])} items")
        
        return jsonify({
            'success': True,
            'request': request_info
        })
        
    except Exception as e:
        print(f"DEBUG: Error in get_single_operations_request: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales/requests/add', methods=['POST'])
@perm('sales_request.create')
def add_sales_request():
    """Add a new sales request with items - Enhanced with duration calculation"""
    print(f"DEBUG: add_sales_request function called")
    
    if 'user_id' not in session:
        print(f"DEBUG: Not authenticated - user_id not in session")
        return jsonify(error="Not authenticated"), 401
    
    print(f"DEBUG: Authentication passed, user_id: {session.get('user_id')}")
    
    try:
        # Handle both JSON and multipart form data
        if request.content_type and 'application/json' in request.content_type:
            data = request.get_json()
            files = []
        else:
            data = request.form.to_dict()
            files = request.files.getlist('documents')
        
        print(f"DEBUG: Received data: {data}")
        
        # Extract and validate basic fields
        client_id = data.get('client_id')
        company_id = data.get('company_id')  # Add company support
        request_types = data.get('request_types', [])  # Support multiple types
        
        # If request_types is a string (from form), convert to list
        if isinstance(request_types, str):
            request_types = [rt.strip() for rt in request_types.split(',')]
        
        # Join request types for storage
        request_type = ','.join(request_types) if request_types else data.get('request_type', 'General')
        
        # Auto-generate title if not provided
        title = data.get('title')
        if not title or title.strip() == '':
            # Get client name for title
            conn, cur = connection()
            client_name = 'Unknown Client'
            if client_id:
                cur.execute("SELECT client_name FROM client WHERE id = %s", (client_id,))
                client_result = cur.fetchone()
                if client_result:
                    client_name = client_result['client_name']
            cur.close()
            conn.close()
            
            # Generate descriptive title
            types_display = ', '.join(request_types[:3]) if request_types else 'General'
            if len(request_types) > 3:
                types_display += f' +{len(request_types) - 3} more'
            
            start_date_str = data.get('start_date', '')
            end_date_str = data.get('end_date', '')
            
            if start_date_str and end_date_str:
                title = f"{client_name} - {types_display} - {start_date_str} to {end_date_str}"
            elif start_date_str:
                title = f"{client_name} - {types_display} - {start_date_str}"
            else:
                title = f"{client_name} - {types_display} Request"
        
        description = data.get('description', '')
        priority = data.get('priority', 'normal')
        start_date = data.get('start_date') or data.get('startDate') or data.get('start-date')
        end_date = data.get('end_date') or data.get('endDate') or data.get('end-date')
        
        # Validate required fields
        if not client_id or client_id == '':
            return jsonify({
                'success': False,
                'error': 'Client is required'
            }), 400
        
        if not start_date or start_date == '':
            return jsonify({
                'success': False,
                'error': 'Start date is required'
            }), 400
        
        # Calculate duration
        duration_days = calculate_duration_days(start_date, end_date)
        
        # Validate dates
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            
            if end_date:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                if end_date_obj < start_date_obj:
                    return jsonify({
                        'success': False,
                        'error': 'End date must be greater than or equal to start date'
                    }), 400
            
            # Check urgent date permissions - NEW: Create approval request instead of blocking
            today = datetime.now().date()
            five_days_from_now = today + timedelta(days=5)
            
            needs_approval = False
            approval_reason = None
            if start_date_obj < five_days_from_now and start_date_obj >= today:
                # Anyone who can approve a request does not need approval.
                if not has('sales_request.approve'):
                    needs_approval = True
                    days_until_start = (start_date_obj - today).days
                    approval_reason = f"Urgent date: Request starts in {days_until_start} day(s)"
                    print(f"DEBUG: Urgent date detected - will create approval request instead of direct sales request")
                    
        except ValueError as ve:
            return jsonify({
                'success': False,
                'error': f'Invalid date format. Expected YYYY-MM-DD format.'
            }), 400
        
        # Parse request_data JSON if provided
        request_data_json = {}
        if data.get('request_data'):
            try:
                if isinstance(data['request_data'], str):
                    request_data_json = json.loads(data['request_data'])
                else:
                    request_data_json = data['request_data']
            except json.JSONDecodeError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid request_data JSON'
                }), 400
        
        # Parse template fields - NEW: Support instance-based structure
        template_fields_data = {}
        template_instances = []
        
        if data.get('template_fields'):
            try:
                if isinstance(data['template_fields'], str):
                    template_fields_data = json.loads(data['template_fields'])
                else:
                    template_fields_data = data['template_fields']
                
                print(f"DEBUG: Received template_fields_data type: {type(template_fields_data)}")
                print(f"DEBUG: template_fields_data keys: {template_fields_data.keys() if isinstance(template_fields_data, dict) else 'N/A'}")
                
                # NEW: Check if this is the new instance-based structure
                if isinstance(template_fields_data, dict) and 'instances' in template_fields_data:
                    template_instances = template_fields_data.get('instances', [])
                    # For backward compatibility, also store flat fields
                    template_fields = template_fields_data.get('flat_fields', {})
                    print(f"DEBUG: ✓ New instance-based template data with {len(template_instances)} instances")
                    for idx, inst in enumerate(template_instances):
                        items_in_inst = inst.get('items', [])
                        print(f"DEBUG:   Instance {idx}: type={inst.get('request_type')}, template_id={inst.get('template_id')}, items={len(items_in_inst)}")
                        if items_in_inst:
                            for item_idx, item in enumerate(items_in_inst):
                                print(f"DEBUG:     Item {item_idx}: {item.get('name')} x {item.get('quantity')} {item.get('unit')}")
                else:
                    # Old flat structure
                    template_fields = template_fields_data
                    print(f"DEBUG: Legacy flat template fields structure")
                    
            except (json.JSONDecodeError, TypeError) as e:
                print(f"DEBUG: Error parsing template_fields: {e}")
                template_fields = {}
                template_instances = []
        else:
            template_fields = {}
            print(f"DEBUG: No template_fields provided in request")
        
        # Add duration to template fields
        if duration_days > 0:
            template_fields['duration_days'] = duration_days
            template_fields['duration'] = f"{duration_days} days"
        
        # Merge template data into request_data
        if template_fields:
            request_data_json['template_fields'] = template_fields
        if template_instances:
            request_data_json['template_instances'] = template_instances
        
        # Add request types to request_data
        request_data_json['request_types'] = request_types
        
        conn, cur = connection()
        
        # Get template code if provided
        template_code = data.get('template_code')
        if not template_code and data.get('template_id'):
            cur.execute("SELECT template_code FROM request_type WHERE id = %s", (data['template_id'],))
            template_result = cur.fetchone()
            if template_result:
                template_code = template_result['template_code']
        
        # NEW: If approval needed, create approval request instead of sales request
        if needs_approval:
            print(f"DEBUG: Creating approval request for urgent date")
            
            # Prepare complete request data for storage
            approval_data = {
                'company_id': company_id,
                'client_id': client_id,
                'request_types': request_types,
                'request_type': request_type,
                'template_code': template_code,
                'title': title,
                'description': description,
                'priority': priority,
                'start_date': start_date,
                'end_date': end_date,
                'duration_days': duration_days,
                'template_fields': {
                    'instances': template_instances,
                    'flat_fields': template_fields
                }
            }
            
            # Insert into approvals table
            cur.execute("""
                INSERT INTO sales_request_approvals 
                (request_type, request_data, requested_by, approval_reason)
                VALUES (%s, %s, %s, %s)
            """, (
                'sales_request',
                json.dumps(approval_data),
                session['username'],
                approval_reason
            ))
            
            approval_id = cur.lastrowid
            conn.commit()
            cur.close()
            conn.close()
            
            # Send notification to admins
            try:
                # send_notification_to_role takes a role name and fans out to its
                # members itself; passing user ids here matched no role at all.
                send_notification_to_role(
                    'admin',
                    'Approval Needed',
                    f'New sales request "{title}" needs approval ({approval_reason})'
                )
            except Exception as notif_error:
                print(f"DEBUG: Failed to send notification: {notif_error}")
            
            return jsonify({
                'success': True,
                'needs_approval': True,
                'approval_id': approval_id,
                'message': f'Request submitted for admin approval. {approval_reason}.',
                'approval_reason': approval_reason
            })
        
        # Otherwise, create sales request directly
        # Try to insert with company_id first, fallback if column doesn't exist
        try:
            cur.execute("""
                INSERT INTO sales_request (company_id, client_id, request_type, template_code, title, 
                                         description, priority, start_date, end_date, request_data, 
                                         created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                company_id,
                client_id,
                request_type,
                template_code,
                title,
                description,
                priority,
                start_date,
                end_date,
                json.dumps(request_data_json) if request_data_json else None,
                session['username']
            ))
        except Exception as e:
            if "Unknown column 'company_id'" in str(e):
                # Fallback without company_id
                cur.execute("""
                    INSERT INTO sales_request (client_id, request_type, template_code, title, 
                                             description, priority, start_date, end_date, request_data, 
                                             created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    client_id,
                    request_type,
                    template_code,
                    title,
                    description,
                    priority,
                    start_date,
                    end_date,
                    json.dumps(request_data_json) if request_data_json else None,
                    session['username']
                ))
            else:
                raise e
        
        request_id = cur.lastrowid
        
        # NEW: Insert template instances into the database
        items_count = 0  # Initialize here to track all items
        if template_instances:
            print(f"DEBUG: Inserting {len(template_instances)} template instances for request {request_id}")
            for idx, instance in enumerate(template_instances):
                try:
                    instance_id = instance.get('instance_id')
                    template_id = instance.get('template_id')
                    instance_request_type = instance.get('request_type')
                    fields = instance.get('fields', {})
                    instance_items = instance.get('items', [])
                    
                    # Insert into sales_request_template_instances table
                    cur.execute("""
                        INSERT INTO sales_request_template_instances 
                        (request_id, template_id, request_type, instance_order, template_data)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        request_id,
                        template_id,
                        instance_request_type,
                        idx,  # Use index as order
                        json.dumps(fields)
                    ))
                    print(f"DEBUG: ✓ Inserted instance {instance_id} (Template {template_id}, Type: {instance_request_type})")
                    
                    # NEW: Insert items for this instance with request_type
                    for item in instance_items:
                        item_name = item.get('name', '')
                        item_qty = float(item.get('quantity', 1))
                        item_unit = item.get('unit', 'pcs')
                        item_desc = item.get('comment', '') or item.get('description', '')
                        item_request_type = item.get('request_type', instance_request_type)
                        
                        # Get new fields: sell_type, rental_days, dimension_calc, include_days_in_calc, include_qty_in_calc
                        item_sell_type = item.get('sell_type', 'rent')
                        item_rental_days = int(item.get('rental_days', 1)) if item.get('rental_days') else 1
                        item_dimension_calc = item.get('dimension_calc', None)
                        item_include_days = 1 if item.get('include_days_in_calc', True) else 0
                        item_include_qty = 1 if item.get('include_qty_in_calc', True) else 0
                        
                        # Collect dimensions in attributes JSON
                        attributes = {}
                        if item.get('width'):
                            attributes['width'] = float(item.get('width'))
                        if item.get('height'):
                            attributes['height'] = float(item.get('height'))
                        if item.get('depth'):
                            attributes['depth'] = float(item.get('depth'))
                        
                        if item_name:
                            try:
                                cur.execute("""
                                    INSERT INTO sales_request_items (request_id, request_type, name, description, qty, unit, sell_type, rental_days, dimension_calc, include_days_in_calc, include_qty_in_calc, attributes)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """, (
                                    request_id,
                                    item_request_type,
                                    item_name,
                                    item_desc,
                                    item_qty,
                                    item_unit,
                                    item_sell_type,
                                    item_rental_days,
                                    item_dimension_calc if item_dimension_calc else None,
                                    item_include_days,
                                    item_include_qty,
                                    json.dumps(attributes) if attributes else None
                                ))
                                item_id = cur.lastrowid
                                items_count += 1
                                print(f"DEBUG: ✓ Inserted item '{item_name}' for request type '{item_request_type}' with sell_type={item_sell_type}, rental_days={item_rental_days}, include_days={item_include_days}")
                                
                                # Handle catalog image path (when item selected from catalog has existing image)
                                catalog_image_path = item.get('catalog_image_path', '')
                                if catalog_image_path and catalog_image_path.strip():
                                    catalog_image_path = catalog_image_path.strip()
                                    print(f"DEBUG: Processing catalog image for item {item_id}: {catalog_image_path}")
                                    
                                    # Check if this image path exists in filesystem
                                    full_image_path = os.path.join(os.getcwd(), catalog_image_path.lstrip('/'))
                                    if os.path.exists(full_image_path):
                                        file_size = os.path.getsize(full_image_path)
                                        image_name = os.path.basename(catalog_image_path)
                                        
                                        # Insert reference to existing catalog image
                                        cur.execute("""
                                            INSERT INTO sales_request_item_images 
                                            (item_id, request_id, image_path, image_name, image_size, display_order, uploaded_by)
                                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                                        """, (
                                            item_id,
                                            request_id,
                                            catalog_image_path.lstrip('/'),  # Store relative path
                                            image_name,
                                            file_size,
                                            0,  # First image from catalog
                                            session.get('username', 'Unknown')
                                        ))
                                        print(f"DEBUG: ✓ Saved catalog image reference for item {item_id}")
                                    else:
                                        print(f"DEBUG: Catalog image not found on disk: {full_image_path}")
                                
                                # Log item creation WITH EXISTING CONNECTION (prevents lock contention)
                                item_data = {
                                    'name': item_name,
                                    'qty': item_qty,
                                    'unit': item_unit,
                                    'description': item_desc,
                                    'sell_type': item_sell_type,
                                    'rental_days': item_rental_days,
                                    'dimension_calc': item_dimension_calc,
                                    'attributes': attributes
                                }
                                log_item_change(
                                    request_id=request_id,
                                    item_id=item_id,
                                    item_name=item_name,
                                    request_type=item_request_type,
                                    action_type='ITEM_ADD',
                                    action_by=(session.get('name') or session.get('username') or 'Unknown'),
                                    new_data=item_data,
                                    conn=conn,
                                    cur=cur
                                )
                                
                                # Save item to catalog (auto-save for future use)
                                # Unique key: name + unit + width + height + depth
                                save_item_to_catalog_internal(
                                    name=item_name,
                                    unit=item_unit,
                                    width=attributes.get('width'),
                                    height=attributes.get('height'),
                                    depth=attributes.get('depth'),
                                    dimension_calc=item_dimension_calc,
                                    description=item_desc,
                                    conn=conn,
                                    cur=cur
                                )
                            except Exception as item_error:
                                # If new columns don't exist, fall back to old structure
                                if "Unknown column" in str(item_error):
                                    cur.execute("""
                                        INSERT INTO sales_request_items (request_id, request_type, name, description, qty, unit, attributes)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    """, (
                                        request_id,
                                        item_request_type,
                                        item_name,
                                        item_desc,
                                        item_qty,
                                        item_unit,
                                        json.dumps(attributes) if attributes else None
                                    ))
                                    items_count += 1
                                    print(f"DEBUG: ✓ Inserted item '{item_name}' (fallback without new columns)")
                                else:
                                    raise item_error
                    
                except Exception as inst_error:
                    # If table doesn't exist yet, log but don't fail the request
                    print(f"DEBUG: Warning - Could not insert template instance: {inst_error}")
                    print(f"DEBUG: This is normal if sales_request_template_instances table hasn't been created yet")
        
        # Parse and insert items - LEGACY SUPPORT (for old forms without instances)
        # Only process if template_instances is empty (backward compatibility)
        if not template_instances:
            items_data = []
            if data.get('items'):
                try:
                    if isinstance(data['items'], str):
                        items_data = json.loads(data['items'])
                    else:
                        items_data = data['items']
                except (json.JSONDecodeError, TypeError):
                    items_data = []
            
            for item in items_data:
                item_name = item.get('name') or item.get('item_name', '')
                item_qty = float(item.get('quantity') or item.get('total_quantity', 1))
                item_desc = item.get('comment') or item.get('description', '')
                item_unit = item.get('unit', 'pcs')
                
                # Collect measurements in attributes JSON
                attributes = {}
                if item.get('width'):
                    attributes['width'] = float(item.get('width'))
                if item.get('height'):
                    attributes['height'] = float(item.get('height'))
                if item.get('depth'):
                    attributes['depth'] = float(item.get('depth'))
                
                if item_name:
                    # Try with request_type column first (if available)
                    try:
                        cur.execute("""
                            INSERT INTO sales_request_items (request_id, request_type, name, description, qty, unit, attributes)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            request_id,
                            'General',  # Default request type for legacy items
                            item_name,
                            item_desc,
                            item_qty,
                            item_unit,
                            json.dumps(attributes) if attributes else None
                        ))
                    except Exception as e:
                        # Fallback without request_type if column doesn't exist
                        if "Unknown column 'request_type'" in str(e):
                            cur.execute("""
                                INSERT INTO sales_request_items (request_id, name, description, qty, unit, attributes)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (
                                request_id,
                                item_name,
                                item_desc,
                                item_qty,
                                item_unit,
                                json.dumps(attributes) if attributes else None
                            ))
                        else:
                            raise e
                    items_count += 1
        
        # Update items count
        print(f"DEBUG: Total items inserted: {items_count}")
        if items_count > 0:
            cur.execute("UPDATE sales_request SET items_count = %s WHERE id = %s", 
                       (items_count, request_id))
            print(f"DEBUG: Updated items_count to {items_count} for request {request_id}")
        else:
            print(f"DEBUG: No items to update (items_count = 0) for request {request_id}")
        
        # Get client name for notification (before closing connection)
        cur.execute("SELECT client_name FROM client WHERE id = %s", (client_id,))
        client_result = cur.fetchone()
        client_name = client_result['client_name'] if client_result else 'Unknown Client'
        
        # Log the request creation WITH SAME CONNECTION (before commit)
        try:
            change_desc = f"New sales request created for client '{client_name}'"
            if request_types:
                change_desc += f" - Request types: {', '.join(request_types)}"
            log_request_change(
                request_id=request_id,
                action_type='CREATE',
                action_by=session.get('username', 'Unknown'),
                change_description=change_desc,
                conn=conn,
                cur=cur
            )
        except Exception as log_error:
            print(f"DEBUG: Failed to log request creation: {log_error}")
        
        # NOW commit and close connection
        conn.commit()
        print(f"DEBUG: Transaction committed for request {request_id}")
        
        cur.close()
        conn.close()
        
        # Send notification to operations team
        try:
            notification_title = f"New Sales Request #{request_id:06d}"
            notification_content = f"A new request has been created by {session.get('username', 'Unknown')} for client '{client_name}'. Duration: {duration_days} days. Please review and add costing."
            notifications_sent = send_notification_to_role('operation', notification_title, notification_content)
            print(f"DEBUG: Sent {notifications_sent} notifications to operations team")
        except Exception as e:
            print(f"DEBUG: Error sending notifications: {e}")
        
        return jsonify({
            'success': True,
            'message': 'Sales request created successfully',
            'request_id': request_id,
            'request_number': f"REQ{request_id:06d}",
            'duration_days': duration_days
        })
        
    except Exception as e:
        print(f"DEBUG: Error in add_sales_request: {e}")
        import traceback
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/sales/requests/<int:request_id>/items', methods=['GET'])
@perm('sales_request.view')
def get_sales_request_items_list(request_id):
    """Get items for a specific sales request - used for credit item selection"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        cur.execute("""
            SELECT 
                sri.id,
                sri.name as item_name,
                sri.qty as quantity,
                sri.cost_per_item,
                sri.sell_per_item,
                sri.approval_status,
                sri.attributes,
                sri.description as specifications
            FROM sales_request_items sri
            WHERE sri.request_id = %s
            ORDER BY sri.id
        """, (request_id,))
        
        items = cur.fetchall()
        
        items_list = []
        for item in items:
            # Parse attributes for dimensions
            attributes = {}
            if item.get('attributes'):
                try:
                    attributes = json.loads(item['attributes']) if isinstance(item['attributes'], str) else item['attributes']
                except:
                    attributes = {}
            
            items_list.append({
                'id': item['id'],
                'item_name': item['item_name'] or 'Unnamed Item',
                'quantity': float(item['quantity']) if item['quantity'] else 1,
                'cost_per_item': float(item['cost_per_item']) if item['cost_per_item'] else 0,
                'sell_per_item': float(item['sell_per_item']) if item['sell_per_item'] else 0,
                'approval_status': item['approval_status'] or 'pending',
                'width': float(attributes.get('width')) if attributes.get('width') else None,
                'height': float(attributes.get('height')) if attributes.get('height') else None,
                'depth': float(attributes.get('depth')) if attributes.get('depth') else None,
                'unit': attributes.get('unit') or 'PCS'
            })
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'items': items_list})
        
    except Exception as e:
        print(f"Error getting request items: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sales/requests/<int:request_id>/files', methods=['GET'])
@perm('sales_request.view')
def get_request_files(request_id):
    """Get files for a sales request"""
    try:
        conn, cur = connection()
        
        cur.execute("""
            SELECT rf.*, u.username as uploaded_by_name
            FROM sales_request_files rf
            LEFT JOIN user u ON rf.uploaded_by = u.id
            WHERE rf.request_id = %s
            ORDER BY rf.uploaded_at DESC
        """, (request_id,))
        
        files = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'files': files
        })
        
    except Exception as e:
        print(f"DEBUG: Error in get_request_files: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales/requests/files/<int:file_id>/download', methods=['GET'])
@perm('sales_request.view')
def download_request_file(file_id):
    """Download a sales request file"""
    try:
        conn, cur = connection()
        
        cur.execute("""
            SELECT file_name, file_path
            FROM sales_request_files
            WHERE id = %s
        """, (file_id,))
        
        file_data = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if not file_data:
            return abort(404)
        
        if not os.path.exists(file_data['file_path']):
            return abort(404)
        
        return send_file(file_data['file_path'], 
                        as_attachment=True, 
                        download_name=file_data['file_name'])
        
    # abort(404) raises an HTTPException; letting the blanket handler below
    # catch it would report a missing file as a server error.
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Error in download_request_file: {e}")
        return abort(500)

@app.route('/api/sales/requests/files/<int:file_id>', methods=['DELETE'])
@perm('sales_request.edit')
def delete_request_file(file_id):
    """Delete a sales request file"""
    try:
        conn, cur = connection()
        
        # Get file info
        cur.execute("""
            SELECT file_path
            FROM sales_request_files
            WHERE id = %s
        """, (file_id,))
        
        file_data = cur.fetchone()
        
        if not file_data:
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
        
        # Delete from database
        cur.execute("DELETE FROM sales_request_files WHERE id = %s", (file_id,))
        
        # Delete physical file
        try:
            if os.path.exists(file_data['file_path']):
                os.remove(file_data['file_path'])
        except Exception as e:
            print(f"DEBUG: Could not delete physical file: {e}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'File deleted successfully'
        })
        
    except Exception as e:
        print(f"DEBUG: Error in delete_request_file: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales/requests/<int:request_id>/status', methods=['POST'])
@perm('sales_request.approve')
def update_request_status(request_id):
    """Update request status with history tracking"""
    try:
        data = request.get_json()
        new_status = data.get('status')
        note = data.get('note', '')
        
        if not new_status:
            return jsonify({
                'success': False,
                'error': 'Status is required'
            }), 400
        
        conn, cur = connection()
        
        # Get current status
        cur.execute("SELECT status FROM sales_request WHERE id = %s", (request_id,))
        current = cur.fetchone()
        
        if not current:
            return jsonify({
                'success': False,
                'error': 'Request not found'
            }), 404
        
        old_status = current['status']
        
        # Update status
        cur.execute("""
            UPDATE sales_request 
            SET status = %s, modified_by = %s, modified_at = NOW()
            WHERE id = %s
        """, (new_status, session['username'], request_id))
        
        # Insert status history
        cur.execute("""
            INSERT INTO sales_request_status_history 
            (request_id, old_status, new_status, changed_by, note)
            VALUES (%s, %s, %s, %s, %s)
        """, (request_id, old_status, new_status, session['username'], note))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Status updated successfully'
        })
        
    except Exception as e:
        print(f"DEBUG: Error in update_request_status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/operations/requests/add', methods=['POST'])
@perm('sales_request.create')
def add_operation_request():
    """Add costs to existing request items (operations role)"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('request_id') or not data.get('items'):
            return jsonify({
                'success': False,
                'error': 'Request ID and items are required'
            }), 400
        
        conn, cur = connection()
        
        # Update item costs (using actual table and column names)
        for item in data['items']:
            if item.get('id') and item.get('unit_cost') is not None:
                cur.execute("""
                    UPDATE items 
                    SET total_cost = %s, item_comment = %s, op_added_by = %s, op_added_date = NOW()
                    WHERE item_id = %s AND request_id = %s
                """, (
                    item['unit_cost'],
                    item.get('notes', ''),
                    session['username'],
                    item['id'],
                    data['request_id']
                ))
        
        # Update request total cost
        cur.execute("""
            UPDATE request 
            SET total_cost = (SELECT SUM(total_cost) FROM items WHERE request_id = %s), 
                operation_added_by = %s, operation_added_date = NOW()
            WHERE request_id = %s
        """, (data['request_id'], session['username'], data['request_id']))
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Send notification to sales team when costing is completed
        try:
            # Get request details for notification
            conn, cur = connection()
            cur.execute("SELECT client_name FROM request WHERE request_id = %s", (data['request_id'],))
            request_result = cur.fetchone()
            client_name = request_result['client_name'] if request_result else 'Unknown Client'
            cur.close()
            conn.close()
            
            notification_title = f"Request #{data['request_id']:06d} Costing Completed"
            notification_content = f"Operations team has completed costing for request #{data['request_id']:06d} (Client: {client_name}). The request is now ready for final pricing review."
            notifications_sent = send_notification_to_role('sales', notification_title, notification_content)
            print(f"DEBUG: Sent {notifications_sent} notifications to sales team for completed costing")
        except Exception as e:
            print(f"DEBUG: Error sending costing completion notifications: {e}")
            # Don't fail the costing update if notification fails
        
        return jsonify({
            'success': True,
            'message': 'Costs updated successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/operations/requests/add-costs', methods=['POST'])
@perm('sales_item.cost')
def add_operation_request_costs():
    """Add costs to existing request items (operations role) - alternative endpoint"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        data = request.get_json()
        
        # Debug logging
        print(f"DEBUG: Received data for add-costs: {data}")
        
        # Validate required fields
        if not data.get('request_id') or not data.get('items'):
            return jsonify({
                'success': False,
                'error': 'Request ID and items are required'
            }), 400
        
        conn, cur = connection()
        
        total_request_cost = 0
        updated_items_log = []
        recosted_negotiations = []
        
        # Update item costs (using correct table and column names)
        user_name = session.get('name', session.get('username', 'Unknown'))
        
        for item in data['items']:
            item_id = item.get('id')
            cost_per_item = item.get('cost_per_item')  # Frontend sends this field
            frontend_total_cost = item.get('total_cost', 0)  # Frontend calculated value
            
            print(f"DEBUG: Processing item {item_id} with cost_per_item: {cost_per_item}, frontend_total_cost: {frontend_total_cost}")
            
            if item_id and cost_per_item is not None:
                # Get current values and item properties for RECALCULATING total_cost with formula
                # Extract dimensions from JSON attributes column
                cur.execute("""
                    SELECT name, cost_per_item as old_cost_per_item, sell_per_item, total_cost as old_total_cost,
                           total_sell, approval_status, negotiation_status, qty, negotiation_count,
                           sell_type, rental_days, dimension_calc, include_days_in_calc, include_qty_in_calc,
                           attributes,
                           JSON_UNQUOTE(JSON_EXTRACT(attributes, '$.width')) as width,
                           JSON_UNQUOTE(JSON_EXTRACT(attributes, '$.height')) as height,
                           JSON_UNQUOTE(JSON_EXTRACT(attributes, '$.depth')) as depth
                    FROM sales_request_items 
                    WHERE id = %s AND request_id = %s
                """, (item_id, data['request_id']))
                
                item_data = cur.fetchone()
                item_name = item_data.get('name', f'Item {item_id}') if item_data else f'Item {item_id}'
                old_cost_per_item = item_data.get('old_cost_per_item') if item_data else None
                was_negotiation = item_data.get('approval_status') == 'pending_negotiation' if item_data else False
                
                # RECALCULATE total_cost using formula: cost_per_item × qty × days × dimension_multiplier
                quantity = float(item_data.get('qty', 1)) if item_data else 1
                sell_type = item_data.get('sell_type', 'rent') if item_data else 'rent'
                rental_days = int(item_data.get('rental_days', 1)) if item_data else 1
                include_days_in_calc = bool(item_data.get('include_days_in_calc', 1)) if item_data else True
                include_qty_in_calc = bool(item_data.get('include_qty_in_calc', 1)) if item_data else True
                dimension_calc = item_data.get('dimension_calc', '') if item_data else ''
                
                # Calculate effective days (only for rent items with include_days enabled)
                effective_days = 1
                if sell_type == 'rent' and include_days_in_calc:
                    effective_days = rental_days
                
                # Calculate effective quantity (only if include_qty_in_calc is enabled)
                effective_qty = quantity if include_qty_in_calc else 1
                
                # Calculate dimension multiplier based on dimension_calc
                dimension_multiplier = 1.0
                if dimension_calc and item_data:
                    # Extract dimensions from JSON, handle NULL/empty values
                    width = float(item_data.get('width')) if item_data.get('width') not in (None, '', 'null') else 0
                    height = float(item_data.get('height')) if item_data.get('height') not in (None, '', 'null') else 0
                    depth = float(item_data.get('depth')) if item_data.get('depth') not in (None, '', 'null') else 0
                    
                    # Normalize dimension_calc string - remove spaces and asterisks for comparison
                    dimension_calc_normalized = dimension_calc.replace('*', '').replace(' ', '').upper()
                    
                    if dimension_calc_normalized == 'W' and width > 0:
                        dimension_multiplier = width
                    elif dimension_calc_normalized == 'H' and height > 0:
                        dimension_multiplier = height
                    elif dimension_calc_normalized == 'D' and depth > 0:
                        dimension_multiplier = depth
                    elif dimension_calc_normalized == 'WH' and width > 0 and height > 0:
                        dimension_multiplier = width * height
                    elif dimension_calc_normalized == 'WD' and width > 0 and depth > 0:
                        dimension_multiplier = width * depth
                    elif dimension_calc_normalized == 'HD' and height > 0 and depth > 0:
                        dimension_multiplier = height * depth
                    elif dimension_calc_normalized == 'WHD' and width > 0 and height > 0 and depth > 0:
                        dimension_multiplier = width * height * depth
                else:
                    width = 0
                    height = 0
                    depth = 0
                
                # Apply the formula: Total Cost = cost_per_item × effective_qty × effective_days × dimension_multiplier
                total_cost = cost_per_item * effective_qty * effective_days * dimension_multiplier
                
                print(f"DEBUG: Calculated total_cost for item {item_id}:")
                print(f"  - cost_per_item: {cost_per_item}")
                print(f"  - quantity: {quantity} (effective_qty: {effective_qty}, include_qty={include_qty_in_calc})")
                print(f"  - effective_days: {effective_days} (sell_type={sell_type}, rental_days={rental_days}, include_days={include_days_in_calc})")
                print(f"  - dimension_multiplier: {dimension_multiplier} (dimension_calc={dimension_calc}, W={width}, H={height}, D={depth})")
                print(f"  - TOTAL_COST: {total_cost}")
                
                # Log price change to history if there's a change in cost
                if old_cost_per_item != cost_per_item and old_cost_per_item is not None:
                    # Determine the status for price history (must be 'current', 'negotiated', or 'rejected')
                    # Use 'current' for regular cost updates
                    price_history_status = 'current'
                    
                    # Calculate profit if we have sell price
                    old_sell = item_data.get('sell_per_item')
                    old_total_sell = item_data.get('total_sell')
                    old_total_cost = item_data.get('old_total_cost')
                    profit_amount = (float(old_total_sell or 0) - float(old_total_cost or 0)) if old_total_sell else 0
                    profit_margin = (profit_amount / float(old_total_cost or 1) * 100) if old_total_cost else 0
                    
                    # Build reason text based on context
                    if was_negotiation:
                        reason_text = f"Recosting after negotiation: Cost updated from {old_cost_per_item} to {cost_per_item}"
                    else:
                        reason_text = f"Cost updated from {old_cost_per_item} to {cost_per_item}"
                    
                    cur.execute("""
                        INSERT INTO sales_request_item_price_history
                        (item_id, request_id, version, cost_per_item, sell_per_item, total_cost, total_sell,
                         profit_amount, profit_margin, status, negotiation_reason, created_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        item_id,
                        data['request_id'],
                        item_data.get('negotiation_count', 0) + 1,
                        old_cost_per_item,
                        old_sell,
                        old_total_cost,
                        old_total_sell,
                        profit_amount,
                        profit_margin,
                        price_history_status,  # Use 'current' instead of action_type
                        reason_text,
                        user_name
                    ))
                    print(f"DEBUG: Logged price history for item {item_id}")
                
                # Update the sales_request_items table with the cost information
                # If item was in negotiation, set negotiation_status to 'negotiated' to signal sales
                # Keep approval_status as 'pending_negotiation' and negotiation_reason for context
                if was_negotiation:
                    cur.execute("""
                        UPDATE sales_request_items 
                        SET cost_per_item = %s, 
                            total_cost = %s,
                            negotiation_status = 'negotiated'
                        WHERE id = %s AND request_id = %s
                    """, (
                        cost_per_item,
                        total_cost,
                        item_id,
                        data['request_id']
                    ))
                else:
                    cur.execute("""
                        UPDATE sales_request_items 
                        SET cost_per_item = %s, total_cost = %s
                        WHERE id = %s AND request_id = %s
                    """, (
                        cost_per_item,
                        total_cost,
                        item_id,
                        data['request_id']
                    ))
                
                # Check if update was successful
                if cur.rowcount == 0:
                    print(f"DEBUG: No rows updated for item_id {item_id}")
                else:
                    print(f"DEBUG: Updated {cur.rowcount} rows for item_id {item_id}")
                    
                    # Track change for logging
                    old_price = f'EGP {old_cost_per_item:.2f}' if old_cost_per_item else 'Not set'
                    new_price = f'EGP {cost_per_item:.2f}'
                    updated_items_log.append(f'{item_name}: {old_price} → {new_price}')

                    if was_negotiation:
                        cur.execute("""
                            SELECT id, status
                            FROM negotiation_requests
                            WHERE item_id = %s
                              AND status = 'pending_costing'
                            ORDER BY id DESC
                            LIMIT 1
                        """, (item_id,))
                        negotiation = cur.fetchone()
                        if negotiation:
                            next_status = transition(
                                negotiation['status'],
                                'operation',
                                'complete_costing'
                            )
                            cur.execute("""
                                UPDATE negotiation_requests
                                SET status = %s,
                                    destination_team = 'pricing',
                                    new_cost_price = %s
                                WHERE id = %s
                            """, (
                                next_status,
                                cost_per_item,
                                negotiation['id']
                            ))
                            cur.execute("""
                                INSERT INTO negotiation_logs
                                    (negotiation_id, action, actor_user_id,
                                     actor_name, notes, old_price, new_price)
                                VALUES (%s, 'recosting_completed', %s, %s,
                                        %s, %s, %s)
                            """, (
                                negotiation['id'],
                                session.get('user_id'),
                                user_name,
                                'Operations completed re-costing and returned the negotiation to Re-Pricing.',
                                old_cost_per_item,
                                cost_per_item
                            ))
                            recosted_negotiations.append(negotiation['id'])
                
                # Accumulate total cost for request-level update
                print(f"DEBUG: Adding {total_cost} to total_request_cost (currently {total_request_cost})")
                total_request_cost += total_cost
                print(f"DEBUG: New total_request_cost: {total_request_cost}")
        
        # Update request total cost by calculating sum of total_cost for all items
        print(f"DEBUG: Updating request {data['request_id']} total cost")
        print(f"DEBUG: Accumulated total_request_cost from loop: {total_request_cost}")
        
        # First check if the request exists
        cur.execute("SELECT id, total_cost FROM sales_request WHERE id = %s", (data['request_id'],))
        existing_request = cur.fetchone()
        if not existing_request:
            print(f"ERROR: Request {data['request_id']} not found in sales_request table!")
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': f'Request #{data["request_id"]} not found'
            }), 404
        
        print(f"DEBUG: Request {data['request_id']} exists. Current total_cost: {existing_request['total_cost']}")
        
        # First, let's verify what's in the items table
        cur.execute("""
            SELECT id, name, cost_per_item, total_cost 
            FROM sales_request_items 
            WHERE request_id = %s
        """, (data['request_id'],))
        debug_items = cur.fetchall()
        print(f"DEBUG: Items in database before request update:")
        total_sum = 0
        for debug_item in debug_items:
            print(f"  Item {debug_item['id']}: {debug_item['name']} - cost_per_item={debug_item['cost_per_item']}, total_cost={debug_item['total_cost']}")
            if debug_item['total_cost']:
                total_sum += float(debug_item['total_cost'])
        print(f"DEBUG: Manual sum of all total_cost values: {total_sum}")
        
        # Use the accumulated total_request_cost instead of subquery
        # This ensures we use the values we just calculated in the loop
        cur.execute("""
            UPDATE sales_request 
            SET total_cost = %s
            WHERE id = %s
        """, (total_request_cost, data['request_id']))
        
        if cur.rowcount == 0:
            print(f"WARNING: UPDATE didn't affect any rows for request_id {data['request_id']}")
            # Still continue - the items were updated successfully
            # Just log a warning
        else:
            print(f"DEBUG: Updated {cur.rowcount} request rows")
        
        # Use the calculated total_request_cost directly instead of re-querying
        # This ensures we return the value we just saved
        final_total_cost = total_request_cost
        
        print(f"DEBUG: Final total_cost to be returned: {final_total_cost}")
        
        # Calculate updated status
        cur.execute("""
            SELECT COUNT(*) as total_items, 
                   COUNT(CASE WHEN cost_per_item IS NOT NULL AND cost_per_item > 0 THEN 1 END) as costed_items
            FROM sales_request_items 
            WHERE request_id = %s
        """, (data['request_id'],))
        status_data = cur.fetchone()
        
        total_items = status_data.get('total_items', 0)
        costed_items = status_data.get('costed_items', 0)
        
        if total_items == 0:
            status = 'No Items'
        elif costed_items == 0:
            status = 'Pending'
        elif costed_items == total_items:
            status = 'Completed'
        else:
            status = 'Pending'  # Partially costed - still pending
        
        conn.commit()
        
        # Log individual costing changes for each item with detailed tracking
        username = (session.get('name') or session.get('username') or 'Unknown')
        try:
            # Log each item's cost change individually for granular tracking
            for item_log in updated_items_log:
                log_request_change(
                    request_id=data['request_id'],
                    action_type='COSTING_UPDATE',
                    action_by=username,
                    field_name='item_cost',
                    old_value=None,
                    new_value=item_log,
                    change_description=f'[Operations - Costing] {item_log}'
                )
            
            # Also log summary
            log_request_change(
                request_id=data['request_id'],
                action_type='COSTING_COMPLETE',
                action_by=username,
                field_name='total_cost',
                old_value=None,
                new_value=f'EGP {final_total_cost:.2f}',
                change_description=f'[Operations - Costing] Updated costs for {len(updated_items_log)} item(s). Total: EGP {final_total_cost:.2f}'
            )
        except Exception as log_error:
            print(f"WARNING: Failed to log cost update: {log_error}")

        if recosted_negotiations:
            try:
                send_notification_to_role(
                    'pricing',
                    f"Request #{data['request_id']:06d} Re-Costing Completed",
                    f"Operations completed re-costing for {len(recosted_negotiations)} negotiated item(s). Re-Pricing can now set the new selling price."
                )
            except Exception as notification_error:
                print(f"WARNING: Failed to notify Pricing: {notification_error}")
        
        cur.close()
        conn.close()
        
        # Send notification to sales team when costing is completed
        if status == 'Completed':
            try:
                # Get request details for notification
                conn_notif, cur_notif = connection()
                cur_notif.execute("""
                    SELECT c.client_name 
                    FROM sales_request sr
                    LEFT JOIN client c ON sr.client_id = c.id
                    WHERE sr.id = %s
                """, (data['request_id'],))
                request_result = cur_notif.fetchone()
                client_name = request_result['client_name'] if request_result else 'Unknown Client'
                cur_notif.close()
                conn_notif.close()
                
                notification_title = f"Request #{data['request_id']:06d} Costing Completed"
                notification_content = f"Operations team has completed costing for request #{data['request_id']:06d} (Client: {client_name}). All items have been costed. Total cost: EGP {final_total_cost:.2f}. The request is ready for final pricing review."
                notifications_sent = send_notification_to_role('sales', notification_title, notification_content)
                print(f"DEBUG: Sent {notifications_sent} notifications to sales team for completed costing")
            except Exception as e:
                print(f"DEBUG: Error sending costing completion notifications: {e}")
                # Don't fail the costing update if notification fails
        
        return jsonify({
            'success': True,
            'message': 'Costs updated successfully',
            'total_cost': float(final_total_cost) if final_total_cost else 0,
            'status': status,
            'total_items': total_items,
            'costed_items': costed_items
        })
        
    except Exception as e:
        print(f"DEBUG: Error in add_operation_request_costs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales/requests/edit/<int:request_id>', methods=['POST'])
@perm('sales_request.edit')
def edit_sales_request(request_id):
    """Edit sales request - Enhanced with duration calculation"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        data = request.get_json()
        
        print(f"DEBUG: Edit request {request_id} data: {data}")
        
        # Verify request exists
        conn, cur = connection()
        cur.execute("SELECT * FROM sales_request WHERE id = %s", (request_id,))
        existing_request = cur.fetchone()
        if existing_request:
            # Own or team scope must not be able to edit somebody else's request.
            assert_scope('sales_request.edit', existing_request.get('owner_user_id'))
        
        if not existing_request:
            return jsonify({
                'success': False,
                'error': 'Request not found'
            }), 404
        
        # Validate required fields
        if not data.get('client_id'):
            return jsonify({
                'success': False,
                'error': 'Client is required'
            }), 400
        
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if not start_date:
            return jsonify({
                'success': False,
                'error': 'Start date is required'
            }), 400
        
        # Calculate duration
        duration_days = calculate_duration_days(start_date, end_date)
        
        # Validate dates
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            
            if end_date:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                if end_date_obj < start_date_obj:
                    return jsonify({
                        'success': False,
                        'error': 'End date must be greater than or equal to start date'
                    }), 400
            
            # Check urgent date permissions
            today = datetime.now().date()
            four_days_from_now = today + timedelta(days=4)
            
            if start_date_obj <= four_days_from_now and start_date_obj >= today:
                if not has('sales_request.approve'):
                    return jsonify({
                        'success': False,
                        'error': 'Admin privileges required for urgent dates (within 4 days)'
                    }), 403
                    
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid date format. Expected YYYY-MM-DD format.'
            }), 400
        
        # Process request types
        request_types = data.get('request_types', [])
        if isinstance(request_types, str):
            request_types = [rt.strip() for rt in request_types.split(',')]
        request_type_str = ','.join(request_types) if request_types else existing_request.get('request_type', 'General')
        
        # Auto-generate title if not provided
        title = data.get('title')
        if not title or title.strip() == '':
            # Get client name
            cur.execute("SELECT client_name FROM client WHERE id = %s", (data['client_id'],))
            client_result = cur.fetchone()
            client_name = client_result['client_name'] if client_result else 'Unknown Client'
            
            types_display = ', '.join(request_types[:3]) if request_types else 'General'
            if len(request_types) > 3:
                types_display += f' +{len(request_types) - 3} more'
            
            if start_date and end_date:
                title = f"{client_name} - {types_display} - {start_date} to {end_date}"
            else:
                title = f"{client_name} - {types_display} Request"
        
        # Process template fields - NEW: Support instance-based structure
        template_fields_data = {}
        template_instances = []
        template_fields = {}
        
        if data.get('template_fields'):
            try:
                if isinstance(data['template_fields'], str):
                    template_fields_data = json.loads(data['template_fields'])
                else:
                    template_fields_data = data['template_fields']
                
                print(f"DEBUG EDIT: Received template_fields_data type: {type(template_fields_data)}")
                print(f"DEBUG EDIT: template_fields_data keys: {template_fields_data.keys() if isinstance(template_fields_data, dict) else 'N/A'}")
                
                # NEW: Check if this is the new instance-based structure
                if isinstance(template_fields_data, dict) and 'instances' in template_fields_data:
                    template_instances = template_fields_data.get('instances', [])
                    # For backward compatibility, also store flat fields
                    template_fields = template_fields_data.get('flat_fields', {})
                    print(f"DEBUG EDIT: ✓ New instance-based template data with {len(template_instances)} instances")
                    for idx, inst in enumerate(template_instances):
                        items_in_inst = inst.get('items', [])
                        print(f"DEBUG EDIT:   Instance {idx}: type={inst.get('request_type')}, template_id={inst.get('template_id')}, items={len(items_in_inst)}")
                        if items_in_inst:
                            for item_idx, item in enumerate(items_in_inst):
                                print(f"DEBUG EDIT:     Item {item_idx}: {item.get('name')} x {item.get('quantity')} {item.get('unit')}")
                else:
                    # Old flat structure
                    template_fields = template_fields_data
                    print(f"DEBUG EDIT: Legacy flat template fields structure")
                    
            except (json.JSONDecodeError, TypeError) as e:
                print(f"DEBUG EDIT: Error parsing template_fields: {e}")
                template_fields = {}
                template_instances = []
        else:
            print(f"DEBUG EDIT: No template_fields provided in request")
        
        # Add duration to template fields
        if duration_days > 0:
            template_fields['duration_days'] = duration_days
            template_fields['duration'] = f"{duration_days} day{'s' if duration_days != 1 else ''}"
        
        # Build request_data JSON
        request_data_json = {
            'request_types': request_types,
            'template_fields': template_fields
        }
        
        # Add template instances to request_data
        if template_instances:
            request_data_json['template_instances'] = template_instances
        
        # Update request
        update_fields = []
        update_values = []
        
        # Add all update fields
        update_fields.extend([
            "client_id = %s",
            "request_type = %s", 
            "title = %s",
            "description = %s",
            "priority = %s",
            "start_date = %s",
            "end_date = %s",
            "request_data = %s",
            "modified_at = NOW()",
            "modified_by = %s"
        ])
        
        update_values.extend([
            data['client_id'],
            request_type_str,
            title,
            data.get('description', ''),
            data.get('priority', 'normal'),
            start_date,
            end_date,
            json.dumps(request_data_json),
            session['username']
        ])
        
        # Check for company_id column
        try:
            if data.get('company_id'):
                cur.execute("DESCRIBE sales_request")
                columns = [col['Field'] for col in cur.fetchall()]
                if 'company_id' in columns:
                    update_fields.insert(0, "company_id = %s")
                    update_values.insert(0, data['company_id'])
        except:
            pass
        
        # Add request_id for WHERE clause
        update_values.append(request_id)
        
        # Execute update
        update_query = f"""
            UPDATE sales_request 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        
        # CRITICAL: Get old items BEFORE deletion for proper comparison
        cur.execute("""
            SELECT id, name, request_type, qty, unit, attributes, cost_per_item, sell_per_item, description
            FROM sales_request_items 
            WHERE request_id = %s 
            ORDER BY name, request_type
        """, (request_id,))
        old_items_list = cur.fetchall()
        print(f"DEBUG EDIT: Retrieved {len(old_items_list)} existing items BEFORE deletion for comparison")
        
        # Debug: Print old items details
        if old_items_list:
            for idx, old_item in enumerate(old_items_list):
                print(f"DEBUG EDIT: Old Item {idx}: name='{old_item['name']}', qty={old_item.get('qty')}, attrs={old_item.get('attributes')}")
        else:
            print(f"DEBUG EDIT: WARNING - No old items found for request {request_id}. This might indicate the request has no items yet.")
        
        # Get old template fields from existing request_data BEFORE update
        old_template_fields = {}
        old_template_instances = []
        if existing_request.get('request_data'):
            try:
                old_request_data = json.loads(existing_request['request_data']) if isinstance(existing_request['request_data'], str) else existing_request['request_data']
                old_template_fields = old_request_data.get('template_fields', {})
                old_template_instances = old_request_data.get('template_instances', [])
                print(f"DEBUG EDIT: Retrieved {len(old_template_instances)} old template instances")
            except:
                pass
        
        # Execute the update query
        cur.execute(update_query, update_values)
        
        # NEW: Delete existing template instances
        try:
            cur.execute("DELETE FROM sales_request_template_instances WHERE request_id = %s", (request_id,))
            print(f"DEBUG EDIT: Deleted existing template instances for request {request_id}")
        # A scope refusal is a 403, not a server error.
        except HTTPException:
            raise
        except Exception as inst_del_error:
            print(f"DEBUG EDIT: Could not delete template instances (table may not exist): {inst_del_error}")
        
        # Delete existing items
        cur.execute("DELETE FROM sales_request_items WHERE request_id = %s", (request_id,))
        print(f"DEBUG EDIT: Deleted existing items for request {request_id}")
        
        # NEW: Insert template instances and their items
        items_count = 0
        if template_instances:
            print(f"DEBUG EDIT: Inserting {len(template_instances)} template instances for request {request_id}")
            for idx, instance in enumerate(template_instances):
                try:
                    instance_id = instance.get('instance_id')
                    template_id = instance.get('template_id')
                    instance_request_type = instance.get('request_type')
                    fields = instance.get('fields', {})
                    instance_items = instance.get('items', [])
                    
                    # Insert into sales_request_template_instances table
                    cur.execute("""
                        INSERT INTO sales_request_template_instances 
                        (request_id, template_id, request_type, instance_order, template_data)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        request_id,
                        template_id,
                        instance_request_type,
                        idx,  # Use index as order
                        json.dumps(fields)
                    ))
                    print(f"DEBUG EDIT: ✓ Inserted instance {instance_id} (Template {template_id}, Type: {instance_request_type})")
                    
                    # NEW: Insert items for this instance with request_type
                    for item in instance_items:
                        item_name = item.get('name', '')
                        item_qty = float(item.get('quantity', 1))
                        item_unit = item.get('unit', 'pcs')
                        item_desc = item.get('comment', '') or item.get('description', '')
                        item_request_type = item.get('request_type', instance_request_type)
                        
                        # Get new fields: sell_type, rental_days, dimension_calc, include_days_in_calc, include_qty_in_calc
                        item_sell_type = item.get('sell_type', 'rent')
                        item_rental_days = int(item.get('rental_days', 1)) if item.get('rental_days') else 1
                        item_dimension_calc = item.get('dimension_calc', None)
                        item_include_days = 1 if item.get('include_days_in_calc', True) else 0
                        item_include_qty = 1 if item.get('include_qty_in_calc', True) else 0
                        
                        # Collect dimensions in attributes JSON
                        attributes = {}
                        if item.get('width'):
                            attributes['width'] = float(item.get('width'))
                        if item.get('height'):
                            attributes['height'] = float(item.get('height'))
                        if item.get('depth'):
                            attributes['depth'] = float(item.get('depth'))
                        
                        if item_name:
                            try:
                                cur.execute("""
                                    INSERT INTO sales_request_items (request_id, request_type, name, description, qty, unit, sell_type, rental_days, dimension_calc, include_days_in_calc, include_qty_in_calc, attributes)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """, (
                                    request_id,
                                    item_request_type,
                                    item_name,
                                    item_desc,
                                    item_qty,
                                    item_unit,
                                    item_sell_type,
                                    item_rental_days,
                                    item_dimension_calc if item_dimension_calc else None,
                                    item_include_days,
                                    item_include_qty,
                                    json.dumps(attributes) if attributes else None
                                ))
                                items_count += 1
                                print(f"DEBUG EDIT: ✓ Inserted item '{item_name}' for request type '{item_request_type}' with sell_type={item_sell_type}, include_days={item_include_days}")
                            except Exception as item_error:
                                # If new columns don't exist, fall back to old structure
                                if "Unknown column" in str(item_error):
                                    cur.execute("""
                                        INSERT INTO sales_request_items (request_id, request_type, name, description, qty, unit, attributes)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    """, (
                                        request_id,
                                        item_request_type,
                                        item_name,
                                        item_desc,
                                        item_qty,
                                        item_unit,
                                        json.dumps(attributes) if attributes else None
                                    ))
                                    items_count += 1
                                    print(f"DEBUG EDIT: ✓ Inserted item '{item_name}' (fallback without new columns)")
                                else:
                                    raise item_error
                    
                except Exception as inst_error:
                    # If table doesn't exist yet, log but don't fail the request
                    print(f"DEBUG EDIT: Warning - Could not insert template instance: {inst_error}")
                    print(f"DEBUG EDIT: This is normal if sales_request_template_instances table hasn't been created yet")
        
        # LEGACY SUPPORT: Handle old items format if no template_instances
        elif data.get('items'):
            print(f"DEBUG EDIT: Processing legacy items format")
            # Parse items
            items_data = data['items']
            if isinstance(items_data, str):
                try:
                    items_data = json.loads(items_data)
                except:
                    items_data = []
            
            # Add new items
            for item in items_data:
                item_name = item.get('name') or item.get('item_name', '')
                item_qty = float(item.get('quantity') or item.get('qty', 1))
                item_desc = item.get('comment') or item.get('description', '')
                item_unit = item.get('unit', 'pcs')
                
                # Collect measurements in attributes JSON
                attributes = {}
                if item.get('width'):
                    attributes['width'] = float(item.get('width'))
                if item.get('height'):
                    attributes['height'] = float(item.get('height'))
                if item.get('depth'):
                    attributes['depth'] = float(item.get('depth'))
                
                if item_name:
                    try:
                        cur.execute("""
                            INSERT INTO sales_request_items (request_id, request_type, name, description, qty, unit, attributes)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            request_id,
                            'General',  # Default request type for legacy items
                            item_name,
                            item_desc,
                            item_qty,
                            item_unit,
                            json.dumps(attributes) if attributes else None
                        ))
                    except Exception as e:
                        # Fallback without request_type if column doesn't exist
                        if "Unknown column 'request_type'" in str(e):
                            cur.execute("""
                                INSERT INTO sales_request_items (request_id, name, description, qty, unit, attributes)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (
                                request_id,
                                item_name,
                                item_desc,
                                item_qty,
                                item_unit,
                                json.dumps(attributes) if attributes else None
                            ))
                        else:
                            raise e
                    items_count += 1
        
        # Update items count
        print(f"DEBUG EDIT: Total items inserted: {items_count}")
        if items_count > 0:
            cur.execute("UPDATE sales_request SET items_count = %s WHERE id = %s", 
                       (items_count, request_id))
            print(f"DEBUG EDIT: Updated items_count to {items_count} for request {request_id}")
        else:
            print(f"DEBUG EDIT: No items to update (items_count = 0) for request {request_id}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Log the update with SMART field-level change detection - ONLY log actual changes
        # NOTE: old_items_list and old_template_fields were retrieved BEFORE deletion above
        try:
            username = (session.get('name') or session.get('username') or 'Unknown')
            changes_logged = 0
            
            # 1. CLIENT CHANGE - Only if actually different
            if str(existing_request.get('client_id')) != str(data.get('client_id')):
                conn2, cur2 = connection()
                cur2.execute("SELECT client_name FROM client WHERE id = %s", (existing_request.get('client_id'),))
                old_client = cur2.fetchone()
                cur2.execute("SELECT client_name FROM client WHERE id = %s", (data['client_id'],))
                new_client = cur2.fetchone()
                cur2.close()
                conn2.close()
                
                old_client_name = old_client['client_name'] if old_client else 'Unknown'
                new_client_name = new_client['client_name'] if new_client else 'Unknown'
                
                log_request_change(
                    request_id=request_id,
                    action_type='UPDATE',
                    action_by=username,
                    field_name='client_id',
                    old_value=old_client_name,
                    new_value=new_client_name,
                    change_description=f"Client changed from '{old_client_name}' to '{new_client_name}'"
                )
                changes_logged += 1
            
            # 2. TITLE CHANGE - Only if actually different
            if existing_request.get('title', '').strip() != title.strip():
                log_request_change(
                    request_id=request_id,
                    action_type='UPDATE',
                    action_by=username,
                    field_name='title',
                    old_value=existing_request.get('title', ''),
                    new_value=title,
                    change_description=f"Title updated"
                )
                changes_logged += 1
            
            # 3. DESCRIPTION CHANGE - Only if actually different
            old_desc = (existing_request.get('description') or '').strip()
            new_desc = (data.get('description') or '').strip()
            if old_desc != new_desc:
                log_request_change(
                    request_id=request_id,
                    action_type='UPDATE',
                    action_by=username,
                    field_name='description',
                    old_value=old_desc,
                    new_value=new_desc,
                    change_description=f"Description updated"
                )
                changes_logged += 1
            
            # 4. PRIORITY CHANGE - Only if actually different
            old_priority = existing_request.get('priority', 'normal')
            new_priority = data.get('priority', 'normal')
            if old_priority != new_priority:
                log_request_change(
                    request_id=request_id,
                    action_type='UPDATE',
                    action_by=username,
                    field_name='priority',
                    old_value=old_priority,
                    new_value=new_priority,
                    change_description=f"Priority changed from '{old_priority}' to '{new_priority}'"
                )
                changes_logged += 1
            
            # 5. DATE CHANGES - Only if actually different
            old_start = existing_request.get('start_date').strftime('%Y-%m-%d') if existing_request.get('start_date') else None
            old_end = existing_request.get('end_date').strftime('%Y-%m-%d') if existing_request.get('end_date') else None
            
            if old_start != start_date:
                log_request_change(
                    request_id=request_id,
                    action_type='UPDATE',
                    action_by=username,
                    field_name='start_date',
                    old_value=old_start,
                    new_value=start_date,
                    change_description=f"Start date changed from '{old_start}' to '{start_date}'"
                )
                changes_logged += 1
            
            if old_end != end_date:
                log_request_change(
                    request_id=request_id,
                    action_type='UPDATE',
                    action_by=username,
                    field_name='end_date',
                    old_value=old_end,
                    new_value=end_date,
                    change_description=f"End date changed from '{old_end}' to '{end_date}'"
                )
                changes_logged += 1
            
            # 6. REQUEST TYPES - Only log added/removed types
            old_request_types = set([rt.strip() for rt in existing_request.get('request_type', '').split(',') if rt.strip()])
            new_request_types = set(request_types) if request_types else set()
            
            added_types = new_request_types - old_request_types
            removed_types = old_request_types - new_request_types
            
            for req_type in added_types:
                log_request_change(
                    request_id=request_id,
                    action_type='UPDATE',
                    action_by=username,
                    field_name='request_type_add',
                    old_value=None,
                    new_value=req_type,
                    change_description=f"Added request type: {req_type}"
                )
                changes_logged += 1
            
            for req_type in removed_types:
                log_request_change(
                    request_id=request_id,
                    action_type='UPDATE',
                    action_by=username,
                    field_name='request_type_remove',
                    old_value=req_type,
                    new_value=None,
                    change_description=f"Removed request type: {req_type}"
                )
                changes_logged += 1
            
            # 7. TEMPLATE FIELDS - Only log fields that actually changed
            for field_key, new_value in template_fields.items():
                old_value = old_template_fields.get(field_key)
                # Convert to strings for comparison to handle different types
                old_val_str = str(old_value) if old_value is not None else ''
                new_val_str = str(new_value) if new_value is not None else ''
                
                if old_val_str != new_val_str:
                    # Find the request type for this field
                    field_request_type = 'General'
                    for inst in template_instances:
                        if field_key in inst.get('fields', {}):
                            field_request_type = inst.get('request_type', 'General')
                            break
                    
                    log_request_change(
                        request_id=request_id,
                        action_type='UPDATE',
                        action_by=username,
                        field_name=f"template_field_{field_key}",
                        old_value=old_val_str,
                        new_value=new_val_str,
                        change_description=f"[{field_request_type}] {field_key.replace('_', ' ').title()} changed"
                    )
                    changes_logged += 1
            
            # 8. ITEMS - Intelligent item comparison
            # Build new items lookup: key = (name, request_type), value = item data
            new_items_lookup = {}
            if template_instances:
                for instance in template_instances:
                    inst_req_type = instance.get('request_type', 'General')
                    for item in instance.get('items', []):
                        item_name = item.get('name', '').strip()
                        if item_name:
                            key = (item_name, inst_req_type)
                            new_items_lookup[key] = item
                            print(f"DEBUG EDIT: New item added to lookup: {key} -> qty={item.get('quantity')}, w={item.get('width')}, h={item.get('height')}, d={item.get('depth')}")
            
            # Build old items lookup
            old_items_lookup = {}
            for old_item in old_items_list:
                item_name = old_item['name'].strip() if old_item['name'] else ''
                item_req_type = old_item.get('request_type', 'General')
                if item_name:
                    key = (item_name, item_req_type)
                    old_items_lookup[key] = old_item
                    # Parse old attributes for debugging
                    old_attrs = {}
                    if old_item.get('attributes'):
                        try:
                            old_attrs = json.loads(old_item['attributes']) if isinstance(old_item['attributes'], str) else old_item['attributes']
                        except:
                            pass
                    print(f"DEBUG EDIT: Old item added to lookup: {key} -> qty={old_item.get('qty')}, w={old_attrs.get('width')}, h={old_attrs.get('height')}, d={old_attrs.get('depth')}")
            
            print(f"DEBUG EDIT: Comparison setup - Old items: {len(old_items_lookup)}, New items: {len(new_items_lookup)}")
            
            # Find added items
            for key, new_item in new_items_lookup.items():
                if key not in old_items_lookup:
                    item_name, req_type = key
                    qty = new_item.get('quantity', 1)
                    unit = new_item.get('unit', 'pcs')
                    log_item_change(
                        request_id=request_id,
                        item_id=None,
                        item_name=item_name,
                        request_type=req_type,
                        action_type='ITEM_ADD',
                        action_by=username,
                        old_data=None,
                        new_data={'name': item_name, 'qty': qty, 'unit': unit},
                        change_description=f"[{req_type}] Added item '{item_name}' (Qty: {qty} {unit})"
                    )
                    changes_logged += 1
            
            # Find removed items
            for key, old_item in old_items_lookup.items():
                if key not in new_items_lookup:
                    item_name, req_type = key
                    log_item_change(
                        request_id=request_id,
                        item_id=old_item['id'],
                        item_name=item_name,
                        request_type=req_type,
                        action_type='ITEM_DELETE',
                        action_by=username,
                        old_data={'name': item_name, 'qty': old_item.get('qty')},
                        new_data=None,
                        change_description=f"[{req_type}] Removed item '{item_name}'"
                    )
                    changes_logged += 1
            
            # Find modified items - compare field by field
            for key in set(old_items_lookup.keys()) & set(new_items_lookup.keys()):
                old_item = old_items_lookup[key]
                new_item = new_items_lookup[key]
                item_name, req_type = key
                
                print(f"DEBUG EDIT: Comparing item '{item_name}' ({req_type})")
                
                # Parse old attributes
                old_attrs = {}
                if old_item.get('attributes'):
                    try:
                        old_attrs = json.loads(old_item['attributes']) if isinstance(old_item['attributes'], str) else old_item['attributes']
                    except:
                        pass
                
                # Helper function to get float value safely
                def get_float(val):
                    try:
                        return float(val) if val else 0.0
                    except:
                        return 0.0
                
                # Compare each field - ONLY log if actually different
                old_qty = get_float(old_item.get('qty', 0))
                new_qty = get_float(new_item.get('quantity', 0))
                print(f"DEBUG EDIT:   Quantity: old={old_qty}, new={new_qty}, diff={abs(old_qty - new_qty)}")
                if abs(old_qty - new_qty) > 0.001:  # Use small epsilon for float comparison
                    log_item_change(
                        request_id=request_id,
                        item_id=old_item['id'],
                        item_name=item_name,
                        request_type=req_type,
                        action_type='ITEM_UPDATE',
                        action_by=username,
                        old_data={'qty': old_qty},
                        new_data={'qty': new_qty},
                        change_description=f"[{req_type}] Item '{item_name}': Quantity changed from {old_qty} to {new_qty}"
                    )
                    changes_logged += 1
                
                # Compare dimensions
                dimension_fields = ['width', 'height', 'depth']
                for dim in dimension_fields:
                    old_dim = get_float(old_attrs.get(dim, 0))
                    new_dim = get_float(new_item.get(dim, 0))
                    print(f"DEBUG EDIT:   {dim}: old={old_dim}, new={new_dim}, diff={abs(old_dim - new_dim)}")
                    if abs(old_dim - new_dim) > 0.001:
                        log_item_change(
                            request_id=request_id,
                            item_id=old_item['id'],
                            item_name=item_name,
                            request_type=req_type,
                            action_type='ITEM_UPDATE',
                            action_by=username,
                            old_data={dim: old_dim},
                            new_data={dim: new_dim},
                            change_description=f"[{req_type}] Item '{item_name}': {dim.capitalize()} changed from {old_dim} to {new_dim}"
                        )
                        changes_logged += 1
                
                # Compare unit
                old_unit = old_item.get('unit', 'pcs')
                new_unit = new_item.get('unit', 'pcs')
                if old_unit != new_unit:
                    log_item_change(
                        request_id=request_id,
                        item_id=old_item['id'],
                        item_name=item_name,
                        request_type=req_type,
                        action_type='ITEM_UPDATE',
                        action_by=username,
                        old_data={'unit': old_unit},
                        new_data={'unit': new_unit},
                        change_description=f"[{req_type}] Item '{item_name}': Unit changed from '{old_unit}' to '{new_unit}'"
                    )
                    changes_logged += 1
                
                # Compare description/comment
                old_desc = (old_item.get('description') or '').strip()
                new_desc = (new_item.get('comment') or new_item.get('description') or '').strip()
                if old_desc != new_desc:
                    log_item_change(
                        request_id=request_id,
                        item_id=old_item['id'],
                        item_name=item_name,
                        request_type=req_type,
                        action_type='ITEM_UPDATE',
                        action_by=username,
                        old_data={'description': old_desc},
                        new_data={'description': new_desc},
                        change_description=f"[{req_type}] Item '{item_name}': Description updated"
                    )
                    changes_logged += 1
            
            print(f"DEBUG EDIT: Logged {changes_logged} actual changes for request {request_id}")
            
            # Only log a summary if there were actual changes
            if changes_logged > 0:
                log_request_change(
                    request_id=request_id,
                    action_type='UPDATE',
                    action_by=username,
                    change_description=f"Request updated - {changes_logged} field(s) changed"
                )
            else:
                print(f"DEBUG EDIT: No actual changes detected for request {request_id} - no dummy logs created")
                
        except Exception as log_error:
            print(f"DEBUG: Failed to log request update: {log_error}")
            import traceback
            print(f"DEBUG: Logging error traceback: {traceback.format_exc()}")
        
        # Send notification if items were updated
        if data.get('items'):
            try:
                notification_title = f"Sales Request #{request_id:06d} Updated"
                notification_content = f"Request updated with {duration_days} days duration. Please review changes."
                send_notification_to_role('operation', notification_title, notification_content)
            except:
                pass
        
        return jsonify({
            'success': True,
            'message': 'Request updated successfully',
            'duration_days': duration_days
        })
        
    # A scope refusal is a 403, not a server error.
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Error in edit_sales_request: {e}")
        import traceback
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
@app.route('/api/operations/requests/edit/<int:request_id>', methods=['POST'])
@perm('sales_request.edit')
def edit_operation_request(request_id):
    """Edit operation request (same as add operation for now)"""
    return add_operation_request()

@app.route('/api/sales/requests/delete/<int:request_id>', methods=['DELETE'])
@perm('sales_request.delete')
def delete_sales_request(request_id):
    """Delete a sales request and all its items"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Check if request exists in sales_request table
        cur.execute("SELECT id, owner_user_id FROM sales_request WHERE id = %s", (request_id,))
        _target = cur.fetchone()
        if _target:
            assert_scope('sales_request.delete', _target.get('owner_user_id'))
        if not _target:
            return jsonify({
                'success': False,
                'error': 'Request not found'
            }), 404
        
        # Delete related records first (foreign key constraints)
        # 1. Delete item attachments first (depends on items)
        cur.execute("""
            DELETE FROM sales_request_item_attachments 
            WHERE item_id IN (SELECT id FROM sales_request_items WHERE request_id = %s)
        """, (request_id,))
        print(f"DEBUG: Deleted item attachments for request {request_id}")
        
        # 2. Delete item price history (depends on items)
        cur.execute("""
            DELETE FROM sales_request_item_price_history WHERE request_id = %s
        """, (request_id,))
        print(f"DEBUG: Deleted price history for request {request_id}")
        
        # 3. Delete client approval logs (depends on items)
        cur.execute("""
            DELETE FROM item_client_approval_log WHERE request_id = %s
        """, (request_id,))
        print(f"DEBUG: Deleted client approval logs for request {request_id}")
        
        # 4. Delete sales request items
        cur.execute("DELETE FROM sales_request_items WHERE request_id = %s", (request_id,))
        print(f"DEBUG: Deleted items for request {request_id}")
        
        # 5. Delete template instances
        cur.execute("DELETE FROM sales_request_template_instances WHERE request_id = %s", (request_id,))
        print(f"DEBUG: Deleted template instances for request {request_id}")
        
        # 6. Delete sales request files
        cur.execute("DELETE FROM sales_request_files WHERE request_id = %s", (request_id,))
        print(f"DEBUG: Deleted files for request {request_id}")
        
        # 7. Delete sales request status history
        cur.execute("DELETE FROM sales_request_status_history WHERE request_id = %s", (request_id,))
        print(f"DEBUG: Deleted status history for request {request_id}")
        
        # 8. Delete change logs
        cur.execute("DELETE FROM sales_request_change_log WHERE request_id = %s", (request_id,))
        print(f"DEBUG: Deleted change logs for request {request_id}")
        
        # 9. Delete comment mentions first, then comments
        cur.execute("""
            DELETE FROM sales_request_comment_mentions 
            WHERE comment_id IN (SELECT id FROM sales_request_comments WHERE request_id = %s)
        """, (request_id,))
        cur.execute("DELETE FROM sales_request_comments WHERE request_id = %s", (request_id,))
        print(f"DEBUG: Deleted comments for request {request_id}")
        
        # 10. Delete inventory links
        cur.execute("DELETE FROM sales_request_inventory_link WHERE sales_request_id = %s", (request_id,))
        print(f"DEBUG: Deleted inventory links for request {request_id}")
        
        # 11. Delete approvals (uses sales_request_id, not request_id)
        cur.execute("DELETE FROM sales_request_approvals WHERE sales_request_id = %s", (request_id,))
        print(f"DEBUG: Deleted approvals for request {request_id}")
        
        # 12. Finally delete the main sales request
        cur.execute("DELETE FROM sales_request WHERE id = %s", (request_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"DEBUG: Successfully deleted sales request {request_id} and all related data")
        
        return jsonify({
            'success': True,
            'message': 'Request deleted successfully'
        })
        
    # A scope refusal is a 403, not a server error.
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Error in delete_sales_request: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales/requests/<int:request_id>/changelog', methods=['GET'])
@perm('sales_request.view')
def get_request_changelog(request_id):
    """Get change log for a sales request"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Check if request exists
        cur.execute("SELECT id FROM sales_request WHERE id = %s", (request_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Request not found'
            }), 404
        
        # Fetch all change logs from sales_request_change_log table
        cur.execute("""
            SELECT 
                id,
                request_id,
                action_type,
                action_by,
                DATE_FORMAT(action_date, '%%Y-%%m-%%d %%H:%%i:%%s') as action_date,
                field_name,
                old_value,
                new_value,
                change_description,
                ip_address
            FROM sales_request_change_log
            WHERE request_id = %s
            ORDER BY action_date DESC
        """, (request_id,))
        
        all_logs = cur.fetchall()
        
        # Format the logs for better readability
        formatted_logs = []
        for log in all_logs:
            formatted_log = dict(log)
            
            # Parse JSON values if they exist and truncate for display
            if formatted_log['old_value']:
                try:
                    old_val = json.loads(formatted_log['old_value'])
                    # Format JSON nicely with max length
                    formatted_log['old_value_full'] = json.dumps(old_val, indent=2)
                    formatted_log['old_value_short'] = json.dumps(old_val)[:100] + ('...' if len(json.dumps(old_val)) > 100 else '')
                except:
                    formatted_log['old_value_full'] = formatted_log['old_value']
                    formatted_log['old_value_short'] = formatted_log['old_value'][:100] + ('...' if len(formatted_log['old_value']) > 100 else '')
            
            if formatted_log['new_value']:
                try:
                    new_val = json.loads(formatted_log['new_value'])
                    formatted_log['new_value_full'] = json.dumps(new_val, indent=2)
                    formatted_log['new_value_short'] = json.dumps(new_val)[:100] + ('...' if len(json.dumps(new_val)) > 100 else '')
                except:
                    formatted_log['new_value_full'] = formatted_log['new_value']
                    formatted_log['new_value_short'] = formatted_log['new_value'][:100] + ('...' if len(formatted_log['new_value']) > 100 else '')
            
            formatted_logs.append(formatted_log)
        
        cur.close()
        conn.close()
        
        print(f"DEBUG: Retrieved {len(all_logs)} change logs for request {request_id}")
        
        return jsonify({
            'success': True,
            'logs': formatted_logs,
            'summary': {
                'total_logs': len(all_logs)
            }
        })
        
    except Exception as e:
        print(f"DEBUG: Error in get_request_changelog: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# APPROVAL SYSTEM API ENDPOINTS
# ============================================================================

@app.route('/api/approvals/pending', methods=['GET'])
@perm('sales_request.approve')
def get_pending_approvals():
    """Get all pending approval requests for admin review"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Get all pending approvals with user info
        cur.execute("""
            SELECT 
                a.*,
                u.name as requested_by_name,
                u.mobile as requested_by_mobile
            FROM sales_request_approvals a
            LEFT JOIN user u ON a.requested_by = u.username
            WHERE a.status = 'pending'
            ORDER BY a.requested_at DESC
        """)
        
        approvals = cur.fetchall()
        
        # Parse JSON data for each approval
        approvals_list = []
        for approval in approvals:
            approval_dict = dict(approval)
            
            # Parse request_data JSON
            if approval_dict.get('request_data'):
                try:
                    approval_dict['request_data'] = json.loads(approval_dict['request_data']) if isinstance(approval_dict['request_data'], str) else approval_dict['request_data']
                except:
                    pass
            
            # Format dates
            if approval_dict.get('requested_at'):
                approval_dict['requested_at'] = approval_dict['requested_at'].strftime('%Y-%m-%d %H:%M:%S')
            
            approvals_list.append(approval_dict)
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'approvals': approvals_list,
            'count': len(approvals_list)
        })
        
    except Exception as e:
        print(f"Error getting pending approvals: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/approvals/<int:approval_id>/approve', methods=['POST'])
@perm('sales_request.approve')
def approve_request(approval_id):
    """Approve a pending request and create the actual sales request"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        data = request.get_json() or {}
        admin_notes = data.get('notes', '')
        
        conn, cur = connection()
        
        # Get the pending approval
        cur.execute("SELECT * FROM sales_request_approvals WHERE id = %s AND status = 'pending'", (approval_id,))
        approval = cur.fetchone()
        
        if not approval:
            return jsonify({
                'success': False,
                'error': 'Approval request not found or already processed'
            }), 404
        
        # Parse the request data
        request_data = json.loads(approval['request_data']) if isinstance(approval['request_data'], str) else approval['request_data']
        
        # Prepare request_types for insertion
        request_types = request_data.get('request_types', [])
        if isinstance(request_types, list):
            request_type_str = ','.join(request_types)
        else:
            request_type_str = request_types if request_types else 'General'
        
        # Handle company_id - convert empty string to None
        company_id = request_data.get('company_id')
        if company_id == '' or company_id == 'null':
            company_id = None
        
        # Create the actual sales request
        # (Similar logic to add_sales_request but using stored data)
        cur.execute("""
            INSERT INTO sales_request (
                company_id, client_id, title, description, priority, status,
                start_date, end_date, template_code, request_type, request_data,
                created_by, sales_added_date, approval_status, approval_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), 'approved', %s)
        """, (
            company_id,
            request_data.get('client_id'),
            request_data.get('title'),
            request_data.get('description', ''),
            request_data.get('priority', 'normal'),
            'submitted',  # Initial status
            request_data.get('start_date'),
            request_data.get('end_date'),
            request_data.get('template_code'),
            request_type_str,
            json.dumps(request_data.get('template_fields', {})),
            approval['requested_by'],  # Original requester
            approval_id
        ))
        
        sales_request_id = cur.lastrowid
        
        # Insert items if any
        items_count = 0
        if request_data.get('template_fields', {}).get('instances'):
            for instance in request_data['template_fields']['instances']:
                for item in instance.get('items', []):
                    cur.execute("""
                        INSERT INTO sales_request_items (
                            request_id, request_type, name, description, qty, unit, attributes
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        sales_request_id,
                        instance.get('request_type'),
                        item.get('name'),
                        item.get('comment', ''),
                        float(item.get('quantity', 1)),
                        item.get('unit', 'pcs'),
                        json.dumps({
                            'width': item.get('width'),
                            'height': item.get('height'),
                            'depth': item.get('depth')
                        }) if any([item.get('width'), item.get('height'), item.get('depth')]) else None
                    ))
                    items_count += 1
        
        # Update items count
        if items_count > 0:
            cur.execute("UPDATE sales_request SET items_count = %s WHERE id = %s", 
                       (items_count, sales_request_id))
        
        # Update approval record
        cur.execute("""
            UPDATE sales_request_approvals 
            SET status = 'approved',
                reviewed_by = %s,
                reviewed_at = NOW(),
                sales_request_id = %s,
                notes = %s
            WHERE id = %s
        """, (session['username'], sales_request_id, admin_notes, approval_id))
        
        conn.commit()
        
        # Log the approval
        log_request_change(
            request_id=sales_request_id,
            action_type='APPROVED',
            action_by=(session.get('name') or session.get('username') or 'Unknown'),
            change_description=f"Request approved by admin after urgent date review"
        )
        
        # Send notification to original requester
        try:
            send_notification_to_role(
                approval['requested_by'],
                'Request Approved',
                f'Your sales request "{request_data.get("title")}" has been approved by {session["username"]}'
            )
        except:
            pass
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Request approved successfully',
            'sales_request_id': sales_request_id
        })
        
    except Exception as e:
        print(f"Error approving request: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/approvals/<int:approval_id>/reject', methods=['POST'])
@perm('sales_request.approve')
def reject_request(approval_id):
    """Reject a pending approval request"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        data = request.get_json() or {}
        rejection_reason = data.get('reason', 'No reason provided')
        
        conn, cur = connection()
        
        # Get the pending approval
        cur.execute("SELECT * FROM sales_request_approvals WHERE id = %s AND status = 'pending'", (approval_id,))
        approval = cur.fetchone()
        
        if not approval:
            return jsonify({
                'success': False,
                'error': 'Approval request not found or already processed'
            }), 404
        
        # Update approval record
        cur.execute("""
            UPDATE sales_request_approvals 
            SET status = 'rejected',
                reviewed_by = %s,
                reviewed_at = NOW(),
                rejection_reason = %s
            WHERE id = %s
        """, (session['username'], rejection_reason, approval_id))
        
        conn.commit()
        
        # Send notification to original requester
        request_data = json.loads(approval['request_data']) if isinstance(approval['request_data'], str) else approval['request_data']
        try:
            send_notification_to_role(
                approval['requested_by'],
                'Request Rejected',
                f'Your sales request "{request_data.get("title")}" was rejected. Reason: {rejection_reason}'
            )
        except:
            pass
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Request rejected successfully'
        })
        
    except Exception as e:
        print(f"Error rejecting request: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/approvals/my-requests', methods=['GET'])
@perm('sales_request.view')
def get_my_pending_requests():
    """Get current user's pending approval requests"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Get user's pending approvals
        cur.execute("""
            SELECT * FROM sales_request_approvals 
            WHERE requested_by = %s 
            ORDER BY requested_at DESC
        """, (session['username'],))
        
        approvals = cur.fetchall()
        
        # Parse JSON data
        approvals_list = []
        for approval in approvals:
            approval_dict = dict(approval)
            
            # Parse request_data
            if approval_dict.get('request_data'):
                try:
                    approval_dict['request_data'] = json.loads(approval_dict['request_data']) if isinstance(approval_dict['request_data'], str) else approval_dict['request_data']
                except:
                    pass
            
            # Format dates
            if approval_dict.get('requested_at'):
                approval_dict['requested_at'] = approval_dict['requested_at'].strftime('%Y-%m-%d %H:%M:%S')
            if approval_dict.get('reviewed_at'):
                approval_dict['reviewed_at'] = approval_dict['reviewed_at'].strftime('%Y-%m-%d %H:%M:%S')
            
            approvals_list.append(approval_dict)
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'approvals': approvals_list,
            'count': len(approvals_list)
        })
        
    except Exception as e:
        print(f"Error getting my pending requests: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# END APPROVAL SYSTEM API ENDPOINTS
# ============================================================================

@app.route('/api/sales/requests/<int:request_id>/set-prices', methods=['POST'])
@perm('sales_item.price')
def set_item_prices(request_id):
    """Set selling prices for items in a sales request"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        data = request.get_json()
        items = data.get('items', [])
        
        if not items:
            return jsonify({
                'success': False,
                'error': 'No items provided'
            }), 400
        
        conn, cur = connection()
        
        # Get username for logging price history
        user_name = session.get('name', session.get('username', 'Unknown'))
        
        # Check if request exists
        cur.execute("SELECT id FROM sales_request WHERE id = %s", (request_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Request not found'
            }), 404
        
        # Update each item's sell_per_item price
        updated_count = 0
        updated_items_log = []
        
        for item in items:
            item_id = item.get('item_id')
            sell_per_item = item.get('sell_per_item')
            
            if item_id and sell_per_item is not None:
                # Get current values and item properties for RECALCULATING total_sell with formula
                # Extract dimensions from JSON attributes column
                cur.execute("""
                    SELECT qty, name, sell_per_item as old_sell_per_item, cost_per_item, 
                           total_cost, total_sell as old_total_sell, negotiation_count,
                           sell_type, rental_days, dimension_calc, include_days_in_calc, include_qty_in_calc,
                           approval_status, negotiation_status,
                           attributes,
                           JSON_UNQUOTE(JSON_EXTRACT(attributes, '$.width')) as width,
                           JSON_UNQUOTE(JSON_EXTRACT(attributes, '$.height')) as height,
                           JSON_UNQUOTE(JSON_EXTRACT(attributes, '$.depth')) as depth
                    FROM sales_request_items 
                    WHERE id = %s AND request_id = %s
                """, (item_id, request_id))
                
                item_data = cur.fetchone()
                if item_data:
                    quantity = float(item_data.get('qty', 1))
                    item_name = item_data.get('name', f'Item {item_id}')
                    old_sell_per_item = item_data.get('old_sell_per_item')
                    was_negotiation = (
                        item_data.get('approval_status') == 'pending_negotiation'
                        and item_data.get('negotiation_status') == 'negotiated'
                    )
                    user_roles = session.get('roles', [])
                    if was_negotiation and not any(
                        role in user_roles for role in ('pricing', 'operation', 'admin')
                    ):
                        cur.close()
                        conn.close()
                        return jsonify({
                            'success': False,
                            'error': 'Pricing role is required to complete a negotiated item'
                        }), 403
                    
                    # RECALCULATE total_sell using formula: sell_per_item × qty × days × dimension_multiplier
                    sell_type = item_data.get('sell_type', 'rent')
                    rental_days = int(item_data.get('rental_days', 1))
                    include_days_in_calc = bool(item_data.get('include_days_in_calc', 1))
                    include_qty_in_calc = bool(item_data.get('include_qty_in_calc', 1))
                    dimension_calc = item_data.get('dimension_calc', '')
                    
                    # Calculate effective days (only for rent items with include_days enabled)
                    effective_days = 1
                    if sell_type == 'rent' and include_days_in_calc:
                        effective_days = rental_days
                    
                    # Calculate effective quantity (only if include_qty_in_calc is enabled)
                    effective_qty = quantity if include_qty_in_calc else 1
                    
                    # Calculate dimension multiplier based on dimension_calc
                    dimension_multiplier = 1.0
                    if dimension_calc:
                        # Extract dimensions from JSON, handle NULL/empty values
                        width = float(item_data.get('width')) if item_data.get('width') not in (None, '', 'null') else 0
                        height = float(item_data.get('height')) if item_data.get('height') not in (None, '', 'null') else 0
                        depth = float(item_data.get('depth')) if item_data.get('depth') not in (None, '', 'null') else 0
                        
                        # Normalize dimension_calc string - remove spaces and asterisks for comparison
                        dimension_calc_normalized = dimension_calc.replace('*', '').replace(' ', '').upper()
                        
                        if dimension_calc_normalized == 'W' and width > 0:
                            dimension_multiplier = width
                        elif dimension_calc_normalized == 'H' and height > 0:
                            dimension_multiplier = height
                        elif dimension_calc_normalized == 'D' and depth > 0:
                            dimension_multiplier = depth
                        elif dimension_calc_normalized == 'WH' and width > 0 and height > 0:
                            dimension_multiplier = width * height
                        elif dimension_calc_normalized == 'WD' and width > 0 and depth > 0:
                            dimension_multiplier = width * depth
                        elif dimension_calc_normalized == 'HD' and height > 0 and depth > 0:
                            dimension_multiplier = height * depth
                        elif dimension_calc_normalized == 'WHD' and width > 0 and height > 0 and depth > 0:
                            dimension_multiplier = width * height * depth
                    
                    # Apply the formula: Total Sell = sell_per_item × effective_qty × effective_days × dimension_multiplier
                    total_sell = sell_per_item * effective_qty * effective_days * dimension_multiplier
                    
                    print(f"DEBUG: Calculated total_sell for item {item_id}:")
                    print(f"  - sell_per_item: {sell_per_item}")
                    print(f"  - quantity: {quantity} (effective_qty: {effective_qty}, include_qty={include_qty_in_calc})")
                    print(f"  - effective_days: {effective_days} (sell_type={sell_type}, rental_days={rental_days}, include_days={include_days_in_calc})")
                    print(f"  - dimension_multiplier: {dimension_multiplier} (dimension_calc={dimension_calc})")
                    print(f"  - TOTAL_SELL: {total_sell}")
                    
                    # Log price change to history if there's a change in sell price
                    if old_sell_per_item != sell_per_item and old_sell_per_item is not None:
                        old_cost = item_data.get('cost_per_item')
                        old_total_cost = item_data.get('total_cost')
                        old_total_sell = item_data.get('old_total_sell')
                        profit_amount = (float(old_total_sell or 0) - float(old_total_cost or 0)) if old_total_sell else 0
                        profit_margin = (profit_amount / float(old_total_cost or 1) * 100) if old_total_cost else 0
                        
                        cur.execute("""
                            INSERT INTO sales_request_item_price_history
                            (item_id, request_id, version, cost_per_item, sell_per_item, total_cost, total_sell,
                             profit_amount, profit_margin, status, negotiation_reason, created_by)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            item_id,
                            request_id,
                            item_data.get('negotiation_count', 0) + 1,
                            old_cost,
                            old_sell_per_item,
                            old_total_cost,
                            old_total_sell,
                            profit_amount,
                            profit_margin,
                            'current',
                            f"Sell price updated from {old_sell_per_item} to {sell_per_item}",
                            user_name
                        ))
                        print(f"DEBUG: Logged sell price history for item {item_id}")
                    
                    # Update the item
                    # If item was in negotiation (awaiting repricing), clear all negotiation fields and set to pending
                    if was_negotiation:
                        cur.execute("""
                            SELECT id, status
                            FROM negotiation_requests
                            WHERE item_id = %s
                              AND status = 'pending_pricing'
                            ORDER BY id DESC
                            LIMIT 1
                        """, (item_id,))
                        active_negotiation = cur.fetchone()
                        if not active_negotiation:
                            cur.close()
                            conn.close()
                            return jsonify({
                                'success': False,
                                'error': f'Item {item_id} is not awaiting a Re-Pricing decision'
                            }), 409

                        cur.execute("""
                            UPDATE sales_request_items 
                            SET sell_per_item = %s, total_sell = %s,
                                approval_status = 'pending',
                                negotiation_status = 'none',
                                negotiation_reason = NULL
                            WHERE id = %s AND request_id = %s
                        """, (sell_per_item, total_sell, item_id, request_id))
                        print(f"DEBUG: Cleared negotiation status for item {item_id} after sales re-pricing (was negotiated)")

                        negotiation_status = transition(
                            active_negotiation['status'],
                            'pricing',
                            'reprice'
                        )
                        cur.execute("""
                            UPDATE negotiation_requests
                            SET status = %s,
                                destination_team = 'pricing',
                                new_selling_price = %s
                            WHERE id = %s
                        """, (
                            negotiation_status,
                            sell_per_item,
                            active_negotiation['id']
                        ))
                        cur.execute("""
                            INSERT INTO negotiation_logs
                                (negotiation_id, action, actor_user_id,
                                 actor_name, notes, old_price, new_price)
                            VALUES (%s, 'repricing_completed', %s, %s,
                                    %s, %s, %s)
                        """, (
                            active_negotiation['id'],
                            session.get('user_id'),
                            user_name,
                            'Re-Pricing completed. Item returned to Client Approval.',
                            old_sell_per_item,
                            sell_per_item
                        ))
                    else:
                        cur.execute("""
                            UPDATE sales_request_items 
                            SET sell_per_item = %s, total_sell = %s
                            WHERE id = %s AND request_id = %s
                        """, (sell_per_item, total_sell, item_id, request_id))
                    
                    updated_count += 1
                    
                    # Track change for logging
                    old_price = f'EGP {old_sell_per_item:.2f}' if old_sell_per_item else 'Not set'
                    new_price = f'EGP {sell_per_item:.2f}'
                    updated_items_log.append(f'{item_name}: {old_price} → {new_price}')
                    
                    print(f"DEBUG: Updated item {item_id} with sell_per_item: {sell_per_item}, total_sell: {total_sell}")
        
        # Calculate total selling price for the request
        cur.execute("""
            SELECT SUM(total_sell) as total_sell
            FROM sales_request_items
            WHERE request_id = %s AND total_sell IS NOT NULL
        """, (request_id,))
        
        result = cur.fetchone()
        total_sell_price = result.get('total_sell', 0) if result else 0
        
        # Update the sales_request table with new total_sell
        cur.execute("""
            UPDATE sales_request 
            SET total_sell = %s
            WHERE id = %s
        """, (total_sell_price, request_id))
        
        conn.commit()
        
        # Log individual selling price changes for each item with detailed tracking
        username = (session.get('name') or session.get('username') or 'Unknown')
        try:
            # Log each item's price change individually for granular tracking
            for item_log in updated_items_log:
                log_request_change(
                    request_id=request_id,
                    action_type='PRICING_UPDATE',
                    action_by=username,
                    field_name='item_selling_price',
                    old_value=None,
                    new_value=item_log,
                    change_description=f'[Sales - Pricing] {item_log}'
                )
            
            # Also log summary
            log_request_change(
                request_id=request_id,
                action_type='PRICING_COMPLETE',
                action_by=username,
                field_name='total_sell',
                old_value=None,
                new_value=f'EGP {total_sell_price:.2f}',
                change_description=f'[Sales - Pricing] Set selling prices for {updated_count} item(s). Total: EGP {total_sell_price:.2f}'
            )
        except Exception as log_error:
            print(f"WARNING: Failed to log selling price update: {log_error}")
        
        cur.close()
        conn.close()
        
        print(f"DEBUG: Successfully updated prices for {updated_count} items in request {request_id}")
        print(f"DEBUG: New total sell price: {total_sell_price}")
        
        return jsonify({
            'success': True,
            'message': f'Successfully updated prices for {updated_count} item(s)',
            'total_sell': total_sell_price
        })
        
    except Exception as e:
        print(f"ERROR: Failed to set prices: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales/requests/<int:request_id>/generate-proposal', methods=['GET'])
@perm('sales_request.view')
def generate_proposal_pdf(request_id):
    """Generate a professional PDF proposal for a fully costed sales request"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Get request details
        cur.execute("""
            SELECT sr.*, c.client_name, c.mobile_number, c.email_address, c.job_title,
                   comp.company_name, comp.address as company_address, 
                   comp.phone_number as company_phone, comp.email_address as company_email
            FROM sales_request sr
            LEFT JOIN client c ON sr.client_id = c.id
            LEFT JOIN company comp ON sr.company_id = comp.id
            WHERE sr.id = %s
        """, (request_id,))
        request_data = cur.fetchone()
        
        if not request_data:
            return jsonify({'success': False, 'error': 'Request not found'}), 404
        
        # Get items with selling prices (only fully costed items)
        # Exclude items rejected by the client — they must not appear in the quotation
        cur.execute("""
            SELECT name, description, qty, unit, sell_per_item, total_sell, attributes
            FROM sales_request_items
            WHERE request_id = %s 
            AND cost_per_item IS NOT NULL AND cost_per_item > 0
            AND sell_per_item IS NOT NULL AND sell_per_item > 0
            AND (approval_status IS NULL OR approval_status <> 'rejected')
            ORDER BY id
        """, (request_id,))
        items = cur.fetchall()
        
        if not items or len(items) == 0:
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'No eligible items found for the quotation (rejected items are excluded). Please ensure approved items are costed and priced.'
            }), 400
        
        cur.close()
        conn.close()
        
        # Create PDF in memory
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, 
                               rightMargin=40, leftMargin=40,
                               topMargin=60, bottomMargin=40)
        
        # Container for the PDF elements
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1565c0'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6
        )
        
        # Company Header with Logo - Centered
        logo_path = os.path.join(os.getcwd(), 'static', 'img', 'branding_gate_logo.jpg')
        
        if os.path.exists(logo_path):
            # Logo exists - create centered header with logo on top and company name below
            logo_img = Image(logo_path, width=100, height=100)
            
            # Create a table to center the logo
            logo_table = Table([[logo_img]], colWidths=[6.5*inch])
            logo_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
            ]))
            
            elements.append(logo_table)
            elements.append(Spacer(1, 0.1*inch))
            
            # Company name below logo - centered
            company_name = Paragraph(
                '<b><font size="18" color="#1a237e">BRANDING GATE</font></b>',
                ParagraphStyle('CompanyName', parent=normal_style, alignment=TA_CENTER)
            )
            elements.append(company_name)
        else:
            # Logo doesn't exist - create text-only header
            company_header = Paragraph(
                '<b><font size="20" color="#1a237e">BRANDING GATE</font></b>',
                ParagraphStyle('CompanyHeader', parent=normal_style, alignment=TA_CENTER)
            )
            elements.append(company_header)
        
        elements.append(Spacer(1, 0.2*inch))
        
        # Horizontal line separator
        elements.append(Table([['']], colWidths=[6.5*inch], style=TableStyle([
            ('LINEABOVE', (0, 0), (-1, 0), 2, colors.HexColor('#4e73df')),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.HexColor('#e3f2fd')),
        ])))
        
        elements.append(Spacer(1, 0.3*inch))
        
        # Title
        elements.append(Paragraph("BUSINESS PROPOSAL", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Proposal date
        proposal_date = datetime.now().strftime('%B %d, %Y')
        date_text = f"<i>Proposal Date: {proposal_date}</i>"
        elements.append(Paragraph(date_text, ParagraphStyle('Date', parent=normal_style, alignment=TA_RIGHT, fontSize=9, textColor=colors.grey)))
        elements.append(Spacer(1, 0.3*inch))
        
        # Client Information Section
        elements.append(Paragraph("CLIENT INFORMATION", heading_style))
        
        client_data = [
            ['Company:', request_data.get('company_name', 'N/A')],
            ['Client Name:', request_data.get('client_name', 'N/A')],
            ['Job Title:', request_data.get('job_title', 'N/A') if request_data.get('job_title') else 'N/A'],
            ['Contact:', request_data.get('mobile_number', 'N/A')],
            ['Email:', request_data.get('email_address', 'N/A')]
        ]
        
        client_table = Table(client_data, colWidths=[1.5*inch, 4*inch])
        client_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e3f2fd')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1565c0')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        
        elements.append(client_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Project Information Section
        elements.append(Paragraph("PROJECT DETAILS", heading_style))
        
        # Parse request types
        request_types = request_data.get('request_type', 'General Services')
        if request_types:
            request_types = ', '.join([rt.strip() for rt in request_types.split(',')])
        
        # Calculate duration
        duration_text = 'N/A'
        if request_data.get('start_date'):
            start_date = request_data['start_date'].strftime('%B %d, %Y')
            if request_data.get('end_date'):
                end_date = request_data['end_date'].strftime('%B %d, %Y')
                days = (request_data['end_date'] - request_data['start_date']).days + 1
                duration_text = f"{start_date} to {end_date} ({days} day{'s' if days != 1 else ''})"
            else:
                duration_text = f"Starting {start_date}"
        
        project_data = [
            ['Request ID:', f"#{request_id:06d}"],
            ['Project Title:', request_data.get('title', 'N/A')],
            ['Service Type:', request_types],
            ['Project Duration:', duration_text],
        ]
        
        if request_data.get('description'):
            project_data.append(['Description:', request_data.get('description', '')])
        
        project_table = Table(project_data, colWidths=[1.5*inch, 4*inch])
        project_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f5e9')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#2e7d32')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        
        elements.append(project_table)
        elements.append(Spacer(1, 0.4*inch))
        
        # Items Section
        elements.append(Paragraph("PROPOSED ITEMS & PRICING", heading_style))
        elements.append(Spacer(1, 0.1*inch))
        
        # Build items table
        items_data = [['#', 'Item Description', 'Qty', 'Unit', 'Unit Price', 'Total Price']]
        
        total_amount = 0
        for idx, item in enumerate(items, 1):
            item_name = item.get('name', 'N/A')
            item_desc = item.get('description', '')
            
            # Add dimensions if available
            if item.get('attributes'):
                try:
                    attrs = json.loads(item.get('attributes')) if isinstance(item.get('attributes'), str) else item.get('attributes')
                    dims = []
                    if attrs.get('width'): dims.append(f"W:{attrs['width']}")
                    if attrs.get('height'): dims.append(f"H:{attrs['height']}")
                    if attrs.get('depth'): dims.append(f"D:{attrs['depth']}")
                    if dims:
                        item_desc = f"{item_desc}\n({', '.join(dims)})" if item_desc else f"({', '.join(dims)})"
                except:
                    pass
            
            full_desc = f"{item_name}\n{item_desc}" if item_desc else item_name
            
            qty = float(item.get('qty', 0))
            unit = item.get('unit', 'pcs')
            unit_price = float(item.get('sell_per_item', 0))
            total_price = float(item.get('total_sell', 0))
            total_amount += total_price
            
            items_data.append([
                str(idx),
                Paragraph(full_desc, ParagraphStyle('ItemDesc', parent=normal_style, fontSize=8)),
                f"{qty:.0f}",
                unit,
                f"EGP {unit_price:,.2f}",
                f"EGP {total_price:,.2f}"
            ])
        
        # Add totals
        items_data.append(['', '', '', '', Paragraph('<b>SUBTOTAL:</b>', ParagraphStyle('Bold', parent=normal_style, fontName='Helvetica-Bold')), 
                          Paragraph(f'<b>EGP {total_amount:,.2f}</b>', ParagraphStyle('Bold', parent=normal_style, fontName='Helvetica-Bold'))])
        items_data.append(['', '', '', '', Paragraph('<b>GRAND TOTAL:</b>', ParagraphStyle('Bold', parent=normal_style, fontName='Helvetica-Bold', fontSize=11)), 
                          Paragraph(f'<b>EGP {total_amount:,.2f}</b>', ParagraphStyle('Bold', parent=normal_style, fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#2e7d32')))])
        
        items_table = Table(items_data, colWidths=[0.4*inch, 2.6*inch, 0.6*inch, 0.6*inch, 1*inch, 1.2*inch])
        items_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1565c0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Data rows
            ('FONTSIZE', (0, 1), (-1, -3), 8),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Index column
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),  # Qty column
            ('ALIGN', (3, 1), (3, -1), 'CENTER'),  # Unit column
            ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),  # Price columns
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -3), [colors.white, colors.HexColor('#f5f5f5')]),
            
            # Subtotal row
            ('BACKGROUND', (0, -2), (-1, -2), colors.HexColor('#e3f2fd')),
            ('LINEABOVE', (0, -2), (-1, -2), 1, colors.grey),
            
            # Grand total row
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#c8e6c9')),
            ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#2e7d32')),
            
            # Grid
            ('GRID', (0, 0), (-1, -3), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            
            # Padding
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(items_table)
        elements.append(Spacer(1, 0.4*inch))
        
        # Terms and Conditions
        elements.append(Paragraph("TERMS & CONDITIONS", heading_style))
        
        terms = [
            "1. Prices are quoted in Egyptian Pounds (EGP) and are valid for 30 days from the proposal date.",
            "2. A 50% deposit is required to commence work, with the balance due upon completion.",
            "3. Delivery timelines are subject to confirmation upon order placement.",
            "4. Any modifications to the scope of work may result in price adjustments.",
            "5. Payment terms: Net 30 days from invoice date.",
            "6. This proposal is subject to our standard terms and conditions of service."
        ]
        
        for term in terms:
            elements.append(Paragraph(term, ParagraphStyle('Terms', parent=normal_style, fontSize=8, leftIndent=10, spaceAfter=4)))
        
        elements.append(Spacer(1, 0.3*inch))
        
        # Footer
        footer_style = ParagraphStyle('Footer', parent=normal_style, fontSize=8, alignment=TA_CENTER, textColor=colors.grey)
        elements.append(Paragraph("<i>Thank you for considering our proposal. We look forward to working with you.</i>", footer_style))
        elements.append(Spacer(1, 0.1*inch))
        elements.append(Paragraph(f"<b>Generated by:</b> {session.get('name', session.get('username', 'System'))} | <b>Date:</b> {proposal_date}", footer_style))
        
        # Build PDF
        doc.build(elements)
        
        # Get PDF from buffer
        pdf_data = buffer.getvalue()
        buffer.close()
        
        # Create filename
        safe_client_name = re.sub(r'[^a-zA-Z0-9_-]', '_', request_data.get('client_name', 'Client'))
        filename = f"Proposal_{request_id:06d}_{safe_client_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        # Create response
        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        print(f"ERROR: Failed to generate proposal PDF: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Failed to generate proposal: {str(e)}'
        }), 500

# Comments API endpoints using Firebase
@app.route('/api/requests/<int:request_id>/comments', methods=['GET'])
@perm('sales_request.comment')
def get_request_comments(request_id):
    """Get all comments for a specific request from Firebase"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        # Get comments from Firebase
        comments_ref = db.collection('comments').where('request_id', '==', request_id).order_by('created_at', direction=firestore.Query.DESCENDING)
        comments = comments_ref.stream()
        
        comments_list = []
        for comment in comments:
            comment_data = comment.to_dict()
            comment_data['id'] = comment.id
            # Format timestamp for frontend
            if 'created_at' in comment_data:
                comment_data['created_at'] = comment_data['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            comments_list.append(comment_data)
        
        return jsonify({
            'success': True,
            'comments': comments_list
        })
        
    except Exception as e:
        print(f"DEBUG: Error in get_request_comments: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/requests/<int:request_id>/comments/add', methods=['POST'])
@perm('sales_request.comment')
def add_request_comment(request_id):
    """Add a new comment to a request in Firebase"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('comment'):
            return jsonify({
                'success': False,
                'error': 'Comment text is required'
            }), 400
        
        # Create comment document
        comment_data = {
            'request_id': request_id,
            'user_id': session['user_id'],
            'username': session['username'],
            'comment': data['comment'],
            'created_at': firestore.SERVER_TIMESTAMP
        }
        
        # Add to Firebase
        doc_ref = db.collection('comments').add(comment_data)
        
        return jsonify({
            'success': True,
            'message': 'Comment added successfully',
            'comment_id': doc_ref[1].id
        })
        
    except Exception as e:
        print(f"DEBUG: Error in add_request_comment: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Keep the old routes for backward compatibility
# Dashboard Statistics API endpoints
@app.route('/api/dashboard/sales/statistics', methods=['GET'])
@perm('dashboard.sales')
def get_sales_statistics():
    """Get sales dashboard statistics"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Total requests count
        cur.execute("SELECT COUNT(*) as total FROM request")
        total_requests = cur.fetchone()['total']
        
        # Monthly requests (current month)
        cur.execute("""
            SELECT COUNT(*) as monthly 
            FROM request 
            WHERE MONTH(sales_added_date) = MONTH(CURDATE()) 
            AND YEAR(sales_added_date) = YEAR(CURDATE())
        """)
        monthly_requests = cur.fetchone()['monthly']
        
        # Total value (sum of all request total costs)
        cur.execute("""
            SELECT COALESCE(SUM(r.total_cost), 0) as total_value 
            FROM request r 
            WHERE r.total_cost IS NOT NULL
        """)
        total_value = cur.fetchone()['total_value']
        
        # Pending items count (items without cost)
        cur.execute("""
            SELECT COUNT(*) as pending_items 
            FROM items i 
            WHERE i.total_cost IS NULL OR i.total_cost = 0
        """)
        pending_items = cur.fetchone()['pending_items']
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'statistics': {
                'total_requests': total_requests,
                'monthly_requests': monthly_requests,
                'total_value': float(total_value) if total_value else 0, 
                'pending_items': pending_items
            }
        })
        
    except Exception as e:
        print(f"DEBUG: Error in get_sales_statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/dashboard/operations/statistics', methods=['GET'])
@perm('dashboard.operations')
def get_operations_statistics():
    """Get operations dashboard statistics"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Calculate pending and completed requests based on costing status (using correct tables)
        cur.execute("""
            SELECT 
                COUNT(*) as total_requests,
                COUNT(CASE 
                    WHEN item_stats.total_items = 0 THEN 1
                    WHEN item_stats.costed_items = 0 THEN 1 
                    WHEN item_stats.costed_items < item_stats.total_items THEN 1
                    ELSE NULL 
                END) as pending_requests,
                COUNT(CASE 
                    WHEN item_stats.total_items > 0 AND item_stats.costed_items = item_stats.total_items THEN 1 
                    ELSE NULL 
                END) as completed_requests,
                COUNT(CASE 
                    WHEN item_stats.total_items = 0 THEN 1
                    ELSE NULL 
                END) as no_items_requests
            FROM (
                SELECT sr.id,
                       COUNT(i.id) as total_items,
                       COUNT(CASE WHEN i.cost_per_item IS NOT NULL AND i.cost_per_item > 0 THEN 1 END) as costed_items
                FROM sales_request sr
                LEFT JOIN sales_request_items i ON sr.id = i.request_id
                GROUP BY sr.id
            ) as item_stats
        """)
        
        result = cur.fetchone()
        total_requests = result['total_requests'] 
        pending_requests = result['pending_requests']
        completed_requests = result['completed_requests']
        no_items_requests = result['no_items_requests']
        
        # Total items count
        cur.execute("SELECT COUNT(*) as total_items FROM sales_request_items")
        total_items = cur.fetchone()['total_items']
        
        # Costed items count (items with cost)
        cur.execute("SELECT COUNT(*) as costed_items FROM sales_request_items WHERE cost_per_item IS NOT NULL AND cost_per_item > 0")
        costed_items = cur.fetchone()['costed_items']
        
        # Calculate costing progress percentage
        costing_progress = 0
        if total_items > 0:
            costing_progress = round((costed_items / total_items) * 100, 1)
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'statistics': {
                'total_requests': total_requests,
                'pending_requests': pending_requests,
                'completed_requests': completed_requests,
                'no_items_requests': no_items_requests,
                'total_items': total_items,
                'costed_items': costed_items,
                'costing_progress': costing_progress
            }
        })
        
    except Exception as e:
        print(f"DEBUG: Error in get_operations_statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/dashboard/operations/recent-activity', methods=['GET'])
@perm('dashboard.operations')
def get_operations_recent_activity():
    """Get recent operations activity for dashboard"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Get recent requests with item counts
        cur.execute("""
            SELECT r.request_id, r.client_name, r.sales_added_date,
                   COUNT(i.item_id) as total_items,
                   COUNT(CASE WHEN i.total_cost IS NOT NULL AND i.total_cost > 0 THEN 1 END) as costed_items
            FROM request r
            LEFT JOIN items i ON r.request_id = i.request_id
            GROUP BY r.request_id
            ORDER BY r.sales_added_date DESC
            LIMIT 10
        """)
        
        recent_requests = cur.fetchall()
        
        # Format for frontend
        activity_list = []
        for req in recent_requests:
            # Calculate status
            total_items = req['total_items'] or 0
            costed_items = req['costed_items'] or 0
            
            if total_items == 0:
                status = 'No Items'
            elif costed_items == 0:
                status = 'Pending'
            elif costed_items == total_items:
                status = 'Completed'
            else:
                status = 'Pending'
            
            activity_list.append({
                'request_id': req['request_id'],
                'client_name': req['client_name'],
                'request_date': req['sales_added_date'].strftime('%Y-%m-%d') if req['sales_added_date'] else 'N/A',
                'status': status,
                'total_items': total_items,
                'costed_items': costed_items,
                'progress': round((costed_items / total_items) * 100, 1) if total_items > 0 else 0
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'recent_activity': activity_list
        })
        
    except Exception as e:
        print(f"DEBUG: Error in get_operations_recent_activity: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/dashboard/suppliers/statistics', methods=['GET'])
@perm('dashboard.supplier')
def get_suppliers_statistics():
    """Get supplier statistics for operations dashboard"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Total suppliers count
        cur.execute("SELECT COUNT(*) as total FROM supplier")
        total_suppliers = cur.fetchone()['total']
        
        # Active suppliers (simplified - just count active suppliers)
        cur.execute("""
            SELECT COUNT(*) as active 
            FROM supplier s
            WHERE s.status = 'Active'
        """)
        active_suppliers_result = cur.fetchone()
        active_suppliers = active_suppliers_result['active'] if active_suppliers_result else 0
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'supplier_statistics': {
                'total_suppliers': total_suppliers,
                'active_suppliers': active_suppliers
            }
        })
        
    except Exception as e:
        print(f"DEBUG: Error in get_suppliers_statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Template System API Endpoints

@app.route('/api/sales-requests/templates', methods=['GET'])
@perm('catalog.view')
def get_request_templates():
    """Get all available request templates"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        cur.execute("""
            SELECT id, code, name, template_code 
            FROM request_type 
            WHERE active = 1
            ORDER BY id
        """)
        templates = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'templates': templates
        })
        
    except Exception as e:
        print(f"Error fetching templates: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales-requests/templates/<int:template_id>/fields', methods=['GET'])
@perm('catalog.view')
def get_template_fields(template_id):
    """Get field definitions for a specific template"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        # First get the template_code for this template_id
        cur.execute("SELECT template_code FROM request_type WHERE id = %s", (template_id,))
        template = cur.fetchone()
        
        if not template:
            return jsonify({'success': False, 'error': 'Template not found'}), 404
        
        template_code = template['template_code']
        
        cur.execute("""
            SELECT field_key as field_name, data_type as field_type, required as is_required, 
                   label as field_label, options_json as field_options, '' as validation_rules, 
                   sort_order as display_order
            FROM template_field_def 
            WHERE template_code = %s 
            ORDER BY sort_order, field_key
        """, (template_code,))
        fields = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'fields': fields
        })
        
    except Exception as e:
        print(f"Error fetching template fields: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales-requests/catalog/items', methods=['GET'])
@perm('catalog.view')
def get_catalog_items():
    """Get all catalog items with their descriptions"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        # Template catalog, keyed by template_code. Distinct from item_catalog,
        # which holds the free-form items served by /api/item-catalog.
        # Column names here match the shipped schema: catalog_item has
        # item_label (not item_name) and no type id, and catalog_item_desc
        # joins on the item's primary key rather than its code.
        cur.execute("""
            SELECT ci.id, ci.item_code, ci.item_label AS item_name,
                   ci.template_code,
                   GROUP_CONCAT(cid.desc_label SEPARATOR '|||') AS descriptions
            FROM catalog_item ci
            LEFT JOIN catalog_item_desc cid
                   ON cid.item_id = ci.id AND cid.active = 1
            WHERE ci.active = 1
            GROUP BY ci.id, ci.item_code, ci.item_label, ci.template_code
            ORDER BY ci.template_code, ci.item_label
        """)
        items = cur.fetchall()
        
        # Process descriptions
        for item in items:
            if item['descriptions']:
                item['descriptions'] = item['descriptions'].split('|||')
            else:
                item['descriptions'] = []
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'items': items
        })
        
    except Exception as e:
        print(f"Error fetching catalog items: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales-requests/catalog/item-types', methods=['GET'])
@perm('catalog.view')
def get_catalog_item_types():
    """Get all catalog item types"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        # The shipped table has id / type_code / type_label and no description.
        cur.execute("""
            SELECT id AS item_type_id, type_code, type_label AS type_name
            FROM catalog_item_type
            WHERE active = 1
            ORDER BY type_label
        """)
        types = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'item_types': types
        })
        
    except Exception as e:
        print(f"Error fetching item types: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# ITEM ATTACHMENTS API ENDPOINTS
# ============================================================================

@app.route('/api/sales-requests/items/<int:item_id>/attachments', methods=['POST'])
@perm('sales_request.edit')
def upload_item_attachments(item_id):
    """
    Upload multiple attachments (images/PDFs) for a specific item.
    Supports multiple file upload and stores them organized by item ID.
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        # Check if files are provided
        if 'files[]' not in request.files:
            return jsonify({'success': False, 'message': 'No files provided'}), 400
        
        files = request.files.getlist('files[]')
        request_id = request.form.get('request_id', 'unknown')
        
        # Create item-specific upload directory
        upload_folder = f'uploads/items/{item_id}'
        os.makedirs(upload_folder, exist_ok=True)
        
        uploaded_files = []
        allowed_extensions = {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'}
        max_file_size = 10 * 1024 * 1024  # 10MB
        
        conn, cursor = connection()
        
        # Get item details for logging (item name, request type, request_id)
        cursor.execute("""
            SELECT sri.name as item_name, sri.request_id, 
                   sr.request_type, sr.title as request_title
            FROM sales_request_items sri
            JOIN sales_request sr ON sri.request_id = sr.id
            WHERE sri.id = %s
        """, (item_id,))
        item_info = cursor.fetchone()
        
        if not item_info:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Item not found'}), 404
        
        actual_request_id = item_info['request_id']
        item_name = item_info['item_name']
        request_type = item_info['request_type'] or 'Unknown'
        
        for file in files:
            if file and file.filename:
                # Validate file extension
                if '.' not in file.filename:
                    continue
                
                file_ext = file.filename.rsplit('.', 1)[1].lower()
                if file_ext not in allowed_extensions:
                    print(f"Skipping file {file.filename} - invalid extension: {file_ext}")
                    continue
                
                # Validate file size
                file.seek(0, 2)  # Seek to end
                file_size = file.tell()
                file.seek(0)  # Reset to beginning
                
                if file_size > max_file_size:
                    print(f"Skipping file {file.filename} - size {file_size} exceeds 10MB")
                    continue
                
                # Generate unique filename with timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                safe_filename = secure_filename(file.filename)
                unique_filename = f"{timestamp}_{safe_filename}"
                file_path = os.path.join(upload_folder, unique_filename)
                
                # Save file to disk
                file.save(file_path)
                print(f"Saved file: {file_path} ({file_size} bytes)")
                
                # Insert record into item_images table
                cursor.execute("""
                    INSERT INTO item_images (item_id, image_path, image_type, file_size, uploaded_by, uploaded_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (item_id, file_path, file_ext, file_size, session.get('user_id')))
                
                uploaded_files.append({
                    'filename': unique_filename,
                    'original_name': file.filename,
                    'path': file_path,
                    'size': file_size,
                    'type': file_ext
                })
        
        conn.commit()
        
        # Update item_catalog with first image if this is an image file
        if uploaded_files:
            first_image = None
            image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
            for uf in uploaded_files:
                if uf['type'] in image_extensions:
                    first_image = uf['path']
                    break
            
            if first_image:
                try:
                    # Get item details to find matching catalog entry
                    cursor.execute("""
                        SELECT name, unit, 
                               JSON_EXTRACT(attributes, '$.width') as width,
                               JSON_EXTRACT(attributes, '$.height') as height,
                               JSON_EXTRACT(attributes, '$.depth') as depth
                        FROM sales_request_items
                        WHERE id = %s
                    """, (item_id,))
                    item_details = cursor.fetchone()
                    
                    if item_details:
                        # Parse dimensions from JSON
                        width = float(item_details['width']) if item_details['width'] and str(item_details['width']).strip() not in ('', 'null', 'None', '"null"') else None
                        height = float(item_details['height']) if item_details['height'] and str(item_details['height']).strip() not in ('', 'null', 'None', '"null"') else None
                        depth = float(item_details['depth']) if item_details['depth'] and str(item_details['depth']).strip() not in ('', 'null', 'None', '"null"') else None
                        
                        # Update catalog entry with image (only if image_path is NULL)
                        cursor.execute("""
                            UPDATE item_catalog
                            SET image_path = %s
                            WHERE name = %s 
                            AND unit = %s
                            AND (width <=> %s) AND (height <=> %s) AND (depth <=> %s)
                            AND (image_path IS NULL OR image_path = '')
                        """, (first_image, item_details['name'], item_details['unit'], width, height, depth))
                        
                        if cursor.rowcount > 0:
                            print(f"DEBUG: Updated catalog entry with image: {first_image}")
                        
                        conn.commit()
                except Exception as catalog_err:
                    print(f"DEBUG: Could not update catalog with image: {catalog_err}")
        
        # Log each attachment upload using item-specific logging
        username = (session.get('name') or session.get('username') or 'Unknown')
        for uploaded_file in uploaded_files:
            file_info = {
                'filename': uploaded_file['original_name'],
                'size': uploaded_file['size'],
                'type': uploaded_file['type'],
                'path': uploaded_file['path']
            }
            
            log_item_change(
                request_id=actual_request_id,
                item_id=item_id,
                item_name=item_name,
                request_type=request_type,
                action_type='ATTACHMENT_ADD',
                action_by=username,
                old_data=None,
                new_data=file_info,
                change_description=f"Added attachment '{uploaded_file['original_name']}' ({uploaded_file['size']} bytes)"
            )
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'uploaded_files': uploaded_files,
            'upload_count': len(uploaded_files),
            'item_id': item_id,
            'message': f'Successfully uploaded {len(uploaded_files)} file(s)'
        })
        
    except Exception as e:
        print(f"Error uploading item attachments: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to upload attachments'
        }), 500


@app.route('/api/sales-requests/items/<int:item_id>/attachments', methods=['GET'])
@perm('sales_request.view')
def get_item_attachments(item_id):
    """
    Retrieve all attachments for a specific item.
    Returns list of files with metadata and download URLs.
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        conn, cursor = connection()
        
        cursor.execute("""
            SELECT id, image_path, image_type, file_size, uploaded_at, uploaded_by
            FROM item_images
            WHERE item_id = %s
            ORDER BY uploaded_at DESC
        """, (item_id,))
        
        rows = cursor.fetchall()
        attachments = []
        total_size = 0
        
        for row in rows:
            file_path = row['image_path']
            file_exists = os.path.exists(file_path)
            filename = os.path.basename(file_path)
            
            attachments.append({
                'id': row['id'],
                'path': file_path,
                'filename': filename,
                'type': row['image_type'],
                'size': row['file_size'],
                'size_mb': round(row['file_size'] / (1024 * 1024), 2) if row['file_size'] else 0,
                'uploaded_at': row['uploaded_at'].strftime('%Y-%m-%d %H:%M:%S') if row['uploaded_at'] else None,
                'uploaded_by': row['uploaded_by'],
                'exists': file_exists,
                'url': f'/uploads/items/{item_id}/{filename}' if file_exists else None,
                'is_image': row['image_type'] in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'],
                'is_pdf': row['image_type'] == 'pdf'
            })
            total_size += row['file_size'] or 0
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'attachments': attachments,
            'total_count': len(attachments),
            'total_size': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'item_id': item_id
        })
        
    except Exception as e:
        print(f"Error fetching item attachments: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/sales-requests/items/<int:item_id>/attachments/<int:attachment_id>', methods=['DELETE'])
@perm('sales_request.edit')
def delete_item_attachment(item_id, attachment_id):
    """
    Delete a specific attachment from an item.
    Removes both database record and physical file.
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        conn, cursor = connection()
        
        # Get file path and item details before deleting
        cursor.execute("""
            SELECT ii.image_path, ii.file_size, ii.image_type,
                   sri.name as item_name, sri.request_id,
                   sr.request_type, sr.title as request_title
            FROM item_images ii
            JOIN sales_request_items sri ON ii.item_id = sri.id
            JOIN sales_request sr ON sri.request_id = sr.id
            WHERE ii.id = %s AND ii.item_id = %s
        """, (attachment_id, item_id))
        
        result = cursor.fetchone()
        if not result:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Attachment not found'}), 404
        
        file_path = result['image_path']
        item_name = result['item_name']
        request_id = result['request_id']
        request_type = result['request_type'] or 'Unknown'
        file_size = result['file_size']
        file_type = result['image_type']
        
        # Delete from database
        cursor.execute("DELETE FROM item_images WHERE id = %s", (attachment_id,))
        conn.commit()
        
        # Log the deletion using item-specific logging
        username = (session.get('name') or session.get('username') or 'Unknown')
        filename = os.path.basename(file_path)
        file_info = {
            'filename': filename,
            'size': file_size,
            'type': file_type,
            'path': file_path
        }
        
        log_item_change(
            request_id=request_id,
            item_id=item_id,
            item_name=item_name,
            request_type=request_type,
            action_type='ATTACHMENT_REMOVE',
            action_by=username,
            old_data=file_info,
            new_data=None,
            change_description=f"Removed attachment '{filename}' ({file_size} bytes)"
        )
        
        cursor.close()
        conn.close()
        
        # Delete physical file
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted file: {file_path}")
            
            # Remove directory if empty
            dir_path = os.path.dirname(file_path)
            if os.path.exists(dir_path) and not os.listdir(dir_path):
                os.rmdir(dir_path)
                print(f"Removed empty directory: {dir_path}")
        
        return jsonify({
            'success': True,
            'message': 'Attachment deleted successfully',
            'attachment_id': attachment_id,
            'item_id': item_id
        })
        
    except Exception as e:
        print(f"Error deleting item attachment: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to delete attachment'
        }), 500

# Serve uploaded files for items
@app.route('/uploads/items/<int:item_id>/<filename>')
def serve_item_attachment(item_id, filename):
    """Serve uploaded item attachment files"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        file_path = os.path.join('uploads', 'items', str(item_id), filename)
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': 'File not found'}), 404
        
        # Determine mimetype based on extension
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        mimetype_map = {
            'pdf': 'application/pdf',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'bmp': 'image/bmp',
            'webp': 'image/webp'
        }
        
        mimetype = mimetype_map.get(file_ext, 'application/octet-stream')
        
        return send_file(file_path, mimetype=mimetype, as_attachment=False)
        
    except Exception as e:
        print(f"Error serving item attachment: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# END ITEM ATTACHMENTS API ENDPOINTS
# ============================================================================

@app.route('/api/sales-requests/create-with-template', methods=['POST'])
@perm('sales_request.create')
def create_request_with_template():
    """Create a new sales request using template system"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        data = request.get_json()
        print(f"DEBUG: Creating request with template data: {data}")
        
        # Validate required fields
        if not data.get('template_id'):
            return jsonify({
                'success': False,
                'error': 'Template ID is required'
            }), 400
        
        conn, cur = connection()
        
        # Check if we have client_id or can get it from template_fields client_name
        client_id = data.get('client_id')
        client_name_from_template = data.get('template_fields', {}).get('client_name')
        
        if not client_id and client_name_from_template:
            # Try to get client_id from client_name in template_fields
            cur.execute("SELECT id FROM client WHERE client_name = %s", (client_name_from_template,))
            client_result = cur.fetchone()
            if client_result:
                client_id = client_result['id']
                data['client_id'] = client_id  # Update data for later use
        
        # Check if we have company_id or can get it from template_fields company_name
        company_id = data.get('company_id')
        company_name_from_template = data.get('template_fields', {}).get('company_name')
        
        if not company_id and company_name_from_template:
            # Try to get company_id from company_name in template_fields
            cur.execute("SELECT id FROM company WHERE company_name = %s", (company_name_from_template,))
            company_result = cur.fetchone()
            if company_result:
                company_id = company_result['id']
                data['company_id'] = company_id  # Update data for later use
        
        if not client_id:
            return jsonify({
                'success': False,
                'error': 'Client ID is required'
            }), 400
        
        print(f"DEBUG: Working with client_id: {client_id}, company_id: {company_id}")
        
        # Validate template exists
        cur.execute("SELECT name FROM request_type WHERE id = %s", (data['template_id'],))
        template = cur.fetchone()
        if not template:
            return jsonify({
                'success': False,
                'error': 'Invalid template ID'
            }), 400
        
        # Get template code for this template
        cur.execute("SELECT template_code FROM request_type WHERE id = %s", (data['template_id'],))
        template_info = cur.fetchone()
        template_code = template_info['template_code'] if template_info else 'T1'
        
        # Get template field definitions for validation
        cur.execute("""
            SELECT field_key as field_name, data_type as field_type, required as is_required, '' as validation_rules
            FROM template_field_def 
            WHERE template_code = %s
        """, (template_code,))
        field_defs = cur.fetchall()
        
        # Get client_name from client_id for template fields that might need it
        client_name = None
        client_data = {}
        if data.get('client_id'):
            # Get all available client data in one query to avoid repeated column checks
            try:
                cur.execute("SELECT * FROM client WHERE id = %s", (data['client_id'],))
                client_result = cur.fetchone()
                if client_result:
                    client_data = dict(client_result)
                    client_name = client_result.get('client_name')
                    print(f"DEBUG: Found client_name '{client_name}' for client_id {data['client_id']}")
                    print(f"DEBUG: Available client columns: {list(client_data.keys())}")
            except Exception as e:
                print(f"DEBUG: Error querying client data: {e}")
        
        # Get company_name from company_id for template fields that might need it
        company_name = None
        if data.get('company_id'):
            cur.execute("SELECT company_name FROM company WHERE id = %s", (data['company_id'],))
            company_result = cur.fetchone()
            if company_result:
                company_name = company_result['company_name']
                print(f"DEBUG: Found company_name '{company_name}' for company_id {data['company_id']}")
        elif client_name:
            # If no company_id provided, try to get company from client
            cur.execute("SELECT c.company_name FROM client cl JOIN company c ON cl.company_id = c.id WHERE cl.id = %s", (data['client_id'],))
            company_result = cur.fetchone()
            if company_result:
                company_name = company_result['company_name']
                print(f"DEBUG: Found company_name '{company_name}' from client relationship")
        
        # Validate template-specific fields
        template_fields = data.get('template_fields', {})
        print(f"DEBUG: Starting template field validation. Received template_fields: {template_fields}")
        print(f"DEBUG: Template field definitions: {[f['field_name'] for f in field_defs]}")
        
        for field_def in field_defs:
            field_name = field_def['field_name']
            is_required = field_def['is_required']
            field_type = field_def['field_type']
            
            # Special handling for client_name field - auto-populate from client_id
            if field_name == 'client_name' and client_name and field_name not in template_fields:
                template_fields[field_name] = client_name
                print(f"DEBUG: Auto-populated client_name field with '{client_name}'")
                continue
            
            # Special handling for company_name field - auto-populate from company_id or client relationship
            if field_name == 'company_name' and field_name not in template_fields:
                if company_name:
                    template_fields[field_name] = company_name
                    print(f"DEBUG: Auto-populated company_name field with '{company_name}'")
                    continue
                elif client_name:
                    # Fallback: use client_name as company_name if no company found
                    template_fields[field_name] = f"{client_name} Company"
                    print(f"DEBUG: Auto-populated company_name field with fallback '{client_name} Company'")
                    continue
            
            # Special handling for event_date field - auto-populate from start_date if available
            if field_name == 'event_date' and field_name not in template_fields:
                event_date = data.get('start_date') or data.get('event_date')
                if event_date:
                    template_fields[field_name] = event_date
                    print(f"DEBUG: Auto-populated event_date field with '{event_date}'")
                    continue
                else:
                    # Fallback: use current date if no event date provided
                    current_date = datetime.now().strftime('%Y-%m-%d')
                    template_fields[field_name] = current_date
                    print(f"DEBUG: Auto-populated event_date field with current date '{current_date}'")
                    continue

            # Special handling for setup_date field - ensure it's within start and end date
            if field_name == 'setup_date' and field_name not in template_fields:
                setup_date = data.get('setup_date')
                if setup_date:
                    # Validate that setup_date is within request start and end dates
                    start_date = data.get('start_date')
                    end_date = data.get('end_date')
                    if start_date and end_date:
                        try:
                            setup_dt = datetime.strptime(setup_date, '%Y-%m-%d')
                            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                            
                            if start_dt <= setup_dt <= end_dt:
                                template_fields[field_name] = setup_date
                                print(f"DEBUG: Auto-populated setup_date field with '{setup_date}' (validated within request dates)")
                            else:
                                print(f"WARNING: Setup date '{setup_date}' is outside request date range ({start_date} to {end_date})")
                        except Exception as e:
                            print(f"WARNING: Error validating setup_date: {e}")
                    else:
                        template_fields[field_name] = setup_date
                        print(f"DEBUG: Auto-populated setup_date field with '{setup_date}' (no date range validation)")
                    continue

            # Special handling for dismantle_date field - no date range validation required
            if field_name == 'dismantle_date' and field_name not in template_fields:
                dismantle_date = data.get('dismantle_date')
                if dismantle_date:
                    template_fields[field_name] = dismantle_date
                    print(f"DEBUG: Auto-populated dismantle_date field with '{dismantle_date}'")
                    continue

            # Special handling for event_duration field - auto-calculate from start and end dates
            if field_name == 'event_duration' and field_name not in template_fields:
                start_date = data.get('start_date')
                end_date = data.get('end_date')
                if start_date and end_date:
                    try:
                        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                        duration_days = (end_dt - start_dt).days + 1  # +1 to include both start and end days
                        template_fields[field_name] = f"{duration_days} days"
                        print(f"DEBUG: Auto-calculated event_duration field as '{duration_days} days'")
                    except Exception as e:
                        print(f"WARNING: Error calculating event duration: {e}")
                        # Fallback to 1 day if calculation fails
                        template_fields[field_name] = "1 day"
                        print(f"DEBUG: Auto-populated event_duration field with fallback '1 day'")
                    continue
            
            # Special handling for transfer_type field - provide a reasonable default
            if field_name == 'transfer_type' and field_name not in template_fields:
                # Common transfer types for events/requests
                template_fields[field_name] = "Standard"  # Default to standard transfer
                print(f"DEBUG: Auto-populated transfer_type field with default 'Standard'")
                continue
            
            # Special handling for common date fields that might be missing
            if field_name in ['start_date', 'end_date', 'delivery_date', 'deadline'] and field_name not in template_fields:
                date_value = data.get('start_date') or data.get('end_date') or data.get(field_name)
                if date_value:
                    template_fields[field_name] = date_value
                    print(f"DEBUG: Auto-populated {field_name} field with '{date_value}'")
                    continue
            
            # Special handling for contact fields that might be derivable from client
            if field_name in ['contact_person', 'contact_name'] and field_name not in template_fields and client_name:
                # Use cached client data to get contact info
                contact_person = client_data.get('contact_person') or client_data.get('contact_name')
                
                if contact_person:
                    template_fields[field_name] = contact_person
                    print(f"DEBUG: Auto-populated {field_name} field with '{contact_person}'")
                    continue
                else:
                    # Fallback: use "Contact at [Client Name]"
                    template_fields[field_name] = f"Contact at {client_name}"
                    print(f"DEBUG: Auto-populated {field_name} field with fallback 'Contact at {client_name}'")
                    continue
            
            # Special handling for location/venue fields
            if field_name in ['venue', 'location', 'event_location'] and field_name not in template_fields:
                # Use cached client data to get address info
                address = client_data.get('address') or client_data.get('location') or client_data.get('client_address')
                
                if address:
                    template_fields[field_name] = address
                    print(f"DEBUG: Auto-populated {field_name} field with client address '{address}'")
                    continue
                else:
                    # Fallback: use client name as location
                    template_fields[field_name] = f"{client_name} Location"
                    print(f"DEBUG: Auto-populated {field_name} field with fallback '{client_name} Location'")
                    continue
            
            # Special handling for mobile/phone fields
            if field_name in ['mobile', 'phone', 'contact_mobile'] and field_name not in template_fields:
                # Use cached client data to get mobile info
                mobile_number = client_data.get('contact_mobile') or client_data.get('mobile') or client_data.get('phone') or client_data.get('client_mobile')
                
                if mobile_number:
                    template_fields[field_name] = mobile_number
                    print(f"DEBUG: Auto-populated {field_name} field with '{mobile_number}'")
                    continue
                else:
                    # Fallback: use placeholder
                    template_fields[field_name] = "Contact for mobile"
                    print(f"DEBUG: Auto-populated {field_name} field with fallback 'Contact for mobile'")
                    continue
            
            # Final check: if field is still required and missing, try to provide a reasonable default
            if is_required and (field_name not in template_fields or not template_fields[field_name]):
                # Provide reasonable defaults for common field types and specific field names
                if field_name == 'transfer_type':
                    template_fields[field_name] = "Standard"
                    print(f"DEBUG: Auto-populated required transfer_type field with 'Standard'")
                elif field_name in ['priority', 'urgency', 'level']:
                    template_fields[field_name] = "Normal"
                    print(f"DEBUG: Auto-populated required {field_name} field with 'Normal'")
                elif field_name in ['status', 'state']:
                    template_fields[field_name] = "Pending"
                    print(f"DEBUG: Auto-populated required {field_name} field with 'Pending'")
                elif field_name in ['type', 'category']:
                    template_fields[field_name] = "General"
                    print(f"DEBUG: Auto-populated required {field_name} field with 'General'")
                elif field_name in ['method', 'approach']:
                    template_fields[field_name] = "Standard Method"
                    print(f"DEBUG: Auto-populated required {field_name} field with 'Standard Method'")
                elif field_type == 'date':
                    template_fields[field_name] = datetime.now().strftime('%Y-%m-%d')
                    print(f"DEBUG: Auto-populated required date field {field_name} with current date")
                elif field_type == 'datetime':
                    template_fields[field_name] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    print(f"DEBUG: Auto-populated required datetime field {field_name} with current datetime")
                elif field_type in ['text', 'string', 'varchar']:
                    template_fields[field_name] = f"To be determined - {field_name}"
                    print(f"DEBUG: Auto-populated required text field {field_name} with placeholder")
                elif field_type in ['number', 'int', 'float']:
                    template_fields[field_name] = 0
                    print(f"DEBUG: Auto-populated required numeric field {field_name} with 0")
                elif field_type in ['select', 'dropdown', 'enum']:
                    template_fields[field_name] = "Default"
                    print(f"DEBUG: Auto-populated required select field {field_name} with 'Default'")
                else:
                    # Last resort: provide a generic default based on field name
                    template_fields[field_name] = f"Default {field_name}"
                    print(f"DEBUG: Auto-populated required field {field_name} with generic default 'Default {field_name}'")
                    # Don't return error anymore - we'll always provide some default
            
            # Type validation
            if field_name in template_fields and template_fields[field_name]:
                value = template_fields[field_name]
                if field_type == 'date' and value:
                    try:
                        datetime.strptime(value, '%Y-%m-%d')
                    except ValueError:
                        return jsonify({
                            'success': False,
                            'error': f'Invalid date format for {field_name}'
                        }), 400
                elif field_type == 'datetime' and value:
                    try:
                        # Try date format first (YYYY-MM-DD), then datetime format (YYYY-MM-DD HH:MM:SS)
                        if len(value) == 10:  # Date format: YYYY-MM-DD
                            datetime.strptime(value, '%Y-%m-%d')
                        else:  # Full datetime format
                            datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        return jsonify({
                            'success': False,
                            'error': f'Invalid datetime format for {field_name}. Expected YYYY-MM-DD or YYYY-MM-DD HH:MM:SS'
                        }), 400
        
        print(f"DEBUG: Final template_fields after validation: {template_fields}")
        print(f"DEBUG: All required fields satisfied")
        
        # Get all request types from frontend (multiple types can be selected)
        request_types = data.get('request_types', [])
        if not request_types:
            # Fallback to template name if no request_types provided
            request_types = [template['name']]
        
        # Create comma-separated string for database storage
        request_type_str = ','.join(request_types) if request_types else template['name']
        print(f"DEBUG: Request types to save: {request_type_str}")
        
        # Auto-generate dynamic title if not provided
        auto_title = data.get('title')
        if not auto_title or auto_title == '':
            # Generate title from request types and client info
            if request_types:
                request_types_display = '/'.join(request_types[:3])  # Limit to first 3 types
                if len(request_types) > 3:
                    request_types_display += f" +{len(request_types) - 3} more"
            else:
                request_types_display = template['name']
            
            # Add client and company info
            if client_name and company_name:
                auto_title = f"{request_types_display} Request for {client_name} ({company_name})"
            elif client_name:
                auto_title = f"{request_types_display} Request for {client_name}"
            else:
                auto_title = f"{request_types_display} Request from {session.get('username', 'User')}"
            
            print(f"DEBUG: Auto-generated title: '{auto_title}'")
        
        # Validate that end date is greater than or equal to start date
        start_date_value = data.get('start_date')
        end_date_value = data.get('end_date')
        
        if start_date_value and end_date_value:
            try:
                start_date_obj = datetime.strptime(start_date_value, '%Y-%m-%d')
                end_date_obj = datetime.strptime(end_date_value, '%Y-%m-%d')
                
                if end_date_obj < start_date_obj:
                    return jsonify({
                        'success': False,
                        'error': 'End date must be greater than or equal to start date'
                    }), 400
                    
                print(f"DEBUG: Date validation passed - Start: {start_date_value}, End: {end_date_value}")
            except ValueError as e:
                return jsonify({
                    'success': False,
                    'error': f'Invalid date format: {str(e)}'
                }), 400
        
        # Create the request - try with company_id first, fallback if column doesn't exist
        try:
            cur.execute("""
                INSERT INTO sales_request (
                    company_id, client_id, request_type, template_code, title, description, 
                    status, start_date, end_date, request_data, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data.get('company_id'),
                data['client_id'],
                request_type_str,  # Save all request types as comma-separated string
                template_code,
                auto_title,
                data.get('description', ''),
                'submitted',
                data.get('start_date'),
                data.get('end_date'),
                json.dumps(template_fields) if template_fields else None,
                session['username']
            ))
        except Exception as e:
            if "Unknown column 'company_id'" in str(e):
                # Fallback: company_id column doesn't exist yet
                print(f"DEBUG: company_id column not found, using fallback insert")
                cur.execute("""
                    INSERT INTO sales_request (
                        client_id, request_type, template_code, title, description, 
                        status, start_date, end_date, request_data, created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    data['client_id'],
                    request_type_str,  # Save all request types as comma-separated string
                    template_code,
                    auto_title,
                    data.get('description', ''),
                    'submitted',
                    data.get('start_date'),
                    data.get('end_date'),
                    json.dumps(template_fields) if template_fields else None,
                    session['username']
                ))
            else:
                # Re-raise other exceptions
                raise e
        
        request_id = cur.lastrowid
        
        # Template field values are stored in the request_data JSON column above
        # No need for separate field value table - keeping it simple
        print(f"DEBUG: Template fields stored in request_data JSON: {template_fields}")
        
        # Add request items if provided
        items_count = 0
        if data.get('items'):
            for item in data['items']:
                item_name = item.get('name') or item.get('item_name', '')
                item_qty = float(item.get('quantity', 1))
                item_desc = item.get('notes') or item.get('description', '')
                item_unit = item.get('unit', 'pcs')
                
                # Collect measurements in attributes JSON
                attributes = {}
                if item.get('width'):
                    attributes['width'] = float(item.get('width'))
                if item.get('height'):
                    attributes['height'] = float(item.get('height'))
                if item.get('depth'):
                    attributes['depth'] = float(item.get('depth'))
                
                if item_name:
                    cur.execute("""
                        INSERT INTO sales_request_items (
                            request_id, name, description, qty, unit, attributes
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        request_id,
                        item_name,
                        item_desc,
                        item_qty,
                        item_unit,
                        json.dumps(attributes) if attributes else None
                    ))
                    item_id = cur.lastrowid
                    items_count += 1
                    
                    # Handle catalog image path (when item selected from catalog has existing image)
                    catalog_image_path = item.get('catalog_image_path', '')
                    if catalog_image_path and catalog_image_path.strip():
                        catalog_image_path = catalog_image_path.strip()
                        print(f"DEBUG CREATE: Processing catalog image for item {item_id}: {catalog_image_path}")
                        
                        # Check if this image path exists in filesystem
                        full_image_path = os.path.join(os.getcwd(), catalog_image_path.lstrip('/'))
                        if os.path.exists(full_image_path):
                            file_size = os.path.getsize(full_image_path)
                            image_name = os.path.basename(catalog_image_path)
                            
                            # Insert reference to existing catalog image
                            cur.execute("""
                                INSERT INTO sales_request_item_images 
                                (item_id, request_id, image_path, image_name, image_size, display_order, uploaded_by)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (
                                item_id,
                                request_id,
                                catalog_image_path.lstrip('/'),  # Store relative path
                                image_name,
                                file_size,
                                0,  # First image from catalog
                                session.get('username', 'Unknown')
                            ))
                            print(f"DEBUG CREATE: Saved catalog image reference for item {item_id}")
                        else:
                            print(f"DEBUG CREATE: Catalog image not found on disk: {full_image_path}")
        
        # Update items count in main request
        if items_count > 0:
            cur.execute("UPDATE sales_request SET items_count = %s WHERE id = %s", 
                       (items_count, request_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'request_id': request_id,
            'message': 'Request created successfully'
        })
        
    except Exception as e:
        print(f"Error creating request with template: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales-requests/update-with-template/<int:request_id>', methods=['POST'])
@perm('sales_request.edit')
def update_request_with_template(request_id):
    """Update an existing sales request using template system"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        # Handle both JSON and multipart/form-data (for file uploads)
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Parse form data
            data = {}
            data['client_id'] = request.form.get('client_id')
            data['title'] = request.form.get('title')
            data['description'] = request.form.get('description', '')
            data['start_date'] = request.form.get('start_date')
            data['end_date'] = request.form.get('end_date')
            data['template_id'] = request.form.get('template_id')
            data['company_id'] = request.form.get('company_id')
            
            # Parse JSON fields
            if request.form.get('template_fields'):
                data['template_fields'] = json.loads(request.form.get('template_fields'))
            
            # Parse items from form data
            data['items'] = []
            item_index = 0
            while True:
                item_name = request.form.get(f'items[{item_index}][name]')
                if not item_name:
                    break
                
                item = {
                    'name': item_name,
                    'quantity': request.form.get(f'items[{item_index}][quantity]', '1'),
                    'comment': request.form.get(f'items[{item_index}][comment]', ''),
                    'unit': request.form.get(f'items[{item_index}][unit]', 'pcs'),
                    'width': request.form.get(f'items[{item_index}][width]', ''),
                    'height': request.form.get(f'items[{item_index}][height]', ''),
                    'depth': request.form.get(f'items[{item_index}][depth]', ''),
                    'images': request.files.getlist(f'items[{item_index}][images][]')
                }
                data['items'].append(item)
                item_index += 1
        else:
            # Fallback to JSON
            data = request.get_json()
        
        print(f"DEBUG: Updating request {request_id} with template data: {data}")
        
        conn, cur = connection()
        
        # Verify request exists and user has permission to edit
        cur.execute("SELECT * FROM sales_request WHERE id = %s", (request_id,))
        existing_request = cur.fetchone()
        if existing_request:
            # Own or team scope must not be able to edit somebody else's request.
            assert_scope('sales_request.edit', existing_request.get('owner_user_id'))
        if not existing_request:
            return jsonify({
                'success': False,
                'error': 'Request not found'
            }), 404
        
        # Validate required fields
        if not data.get('client_id'):
            return jsonify({
                'success': False,
                'error': 'Client ID is required'
            }), 400
        
        # Get template info if template_id provided
        template_code = None
        if data.get('template_id'):
            cur.execute("SELECT template_code FROM request_type WHERE id = %s", (data['template_id'],))
            template_info = cur.fetchone()
            template_code = template_info['template_code'] if template_info else None
        
        # Process template fields - NEW: Support instance-based structure
        template_fields_data = data.get('template_fields', {})
        template_instances = []
        template_fields = {}
        
        if template_fields_data:
            print(f"DEBUG: Processing template fields for update: keys={template_fields_data.keys() if isinstance(template_fields_data, dict) else 'N/A'}")
            
            # NEW: Check if this is the new instance-based structure
            if isinstance(template_fields_data, dict) and 'instances' in template_fields_data:
                template_instances = template_fields_data.get('instances', [])
                template_fields = template_fields_data.get('flat_fields', {})
                print(f"DEBUG UPDATE-TEMPLATE: ✓ New instance-based template data with {len(template_instances)} instances")
                for idx, inst in enumerate(template_instances):
                    items_in_inst = inst.get('items', [])
                    print(f"DEBUG UPDATE-TEMPLATE:   Instance {idx}: type={inst.get('request_type')}, template_id={inst.get('template_id')}, items={len(items_in_inst)}")
                    if items_in_inst:
                        for item_idx, item in enumerate(items_in_inst):
                            print(f"DEBUG UPDATE-TEMPLATE:     Item {item_idx}: {item.get('name')} x {item.get('quantity')} {item.get('unit')}")
            else:
                # Old flat structure
                template_fields = template_fields_data
                print(f"DEBUG UPDATE-TEMPLATE: Legacy flat template fields structure")
        
        # Process request_types - support multiple types
        request_types = data.get('request_types', [])
        if isinstance(request_types, str):
            request_types = [rt.strip() for rt in request_types.split(',')]
        request_type_str = ','.join(request_types) if request_types else existing_request.get('request_type', 'General')
        print(f"DEBUG: Processing request types for update: {request_types} -> {request_type_str}")
        
        # Validate that end date is greater than or equal to start date
        start_date_value = data.get('start_date')
        end_date_value = data.get('end_date')
        
        if start_date_value and end_date_value:
            try:
                start_date_obj = datetime.strptime(start_date_value, '%Y-%m-%d')
                end_date_obj = datetime.strptime(end_date_value, '%Y-%m-%d')
                
                if end_date_obj < start_date_obj:
                    return jsonify({
                        'success': False,
                        'error': 'End date must be greater than or equal to start date'
                    }), 400
                    
                print(f"DEBUG: Date validation passed for update - Start: {start_date_value}, End: {end_date_value}")
            except ValueError as e:
                return jsonify({
                    'success': False,
                    'error': f'Invalid date format: {str(e)}'
                }), 400
        
        # Update the main request record
        update_fields = []
        update_values = []
        
        # Always update these fields
        if data.get('client_id'):
            update_fields.append("client_id = %s")
            update_values.append(data['client_id'])
        
        if data.get('title'):
            update_fields.append("title = %s")
            update_values.append(data['title'])
        
        if data.get('description') is not None:
            update_fields.append("description = %s")
            update_values.append(data['description'])
        
        if data.get('start_date'):
            update_fields.append("start_date = %s")
            update_values.append(data['start_date'])
        
        if data.get('end_date') is not None:
            update_fields.append("end_date = %s")
            update_values.append(data['end_date'])
        
        # Merge template fields with existing request_data
        # This allows adding new event types without losing existing template data
        if template_fields or template_instances:
            # Get existing request_data
            existing_request_data = json.loads(existing_request.get('request_data', '{}')) if existing_request.get('request_data') else {}
            
            # Merge new fields with existing ones
            merged_request_data = existing_request_data.copy()
            
            if template_fields:
                merged_request_data['template_fields'] = template_fields
            
            # NEW: Add template instances to request_data
            if template_instances:
                merged_request_data['template_instances'] = template_instances
                print(f"DEBUG UPDATE-TEMPLATE: Added {len(template_instances)} template instances to request_data")
            
            # Add request types to request_data
            if request_types:
                merged_request_data['request_types'] = request_types
            
            # Store merged data
            update_fields.append("request_data = %s")
            update_values.append(json.dumps(merged_request_data))
            
            print(f"DEBUG: Merged template data - instances: {len(template_instances)}, request_types: {request_types}")
        
        if template_code:
            update_fields.append("template_code = %s")
            update_values.append(template_code)
        
        # Update request_type field
        if request_types:
            update_fields.append("request_type = %s")
            update_values.append(request_type_str)
        
        # Add company_id if provided (with fallback for missing column)
        if data.get('company_id'):
            try:
                # Test if company_id column exists
                cur.execute("DESCRIBE sales_request")
                columns = [col[0] for col in cur.fetchall()]
                if 'company_id' in columns:
                    update_fields.append("company_id = %s")
                    update_values.append(data['company_id'])
            # A scope refusal is a 403, not a server error.
            except HTTPException:
                raise
            except Exception as e:
                print(f"DEBUG: company_id column check failed: {e}")
        
        # Always update modified timestamp
        update_fields.append("modified_at = NOW()")
        update_fields.append("modified_by = %s")
        update_values.append(session['username'])
        
        # Add request_id for WHERE clause
        update_values.append(request_id)
        
        # Build and execute update query
        update_query = f"""
            UPDATE sales_request 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        
        print(f"DEBUG: Executing update query: {update_query}")
        print(f"DEBUG: With values: {update_values}")
        
        # CRITICAL: Get old items and template data BEFORE any deletion for proper comparison
        cur.execute("""
            SELECT id, name, request_type, qty, unit, attributes, cost_per_item, sell_per_item, description
            FROM sales_request_items 
            WHERE request_id = %s 
            ORDER BY name, request_type
        """, (request_id,))
        old_items_list = cur.fetchall()
        print(f"DEBUG UPDATE-TEMPLATE: Retrieved {len(old_items_list)} existing items BEFORE deletion for comparison")
        
        # Debug: Print old items details
        if old_items_list:
            for idx, old_item in enumerate(old_items_list):
                old_attrs = {}
                if old_item.get('attributes'):
                    try:
                        old_attrs = json.loads(old_item['attributes']) if isinstance(old_item['attributes'], str) else old_item['attributes']
                    except:
                        pass
                print(f"DEBUG UPDATE-TEMPLATE:   Old Item {idx}: '{old_item['name']}' - qty={old_item.get('qty')}, width={old_attrs.get('width')}, height={old_attrs.get('height')}, depth={old_attrs.get('depth')}, unit={old_item.get('unit')}")
        else:
            print(f"DEBUG UPDATE-TEMPLATE: WARNING - No old items found for request {request_id}")
        
        # Get old template fields from existing request_data BEFORE update
        old_template_fields = {}
        old_template_instances = []
        if existing_request.get('request_data'):
            try:
                old_request_data = json.loads(existing_request['request_data']) if isinstance(existing_request['request_data'], str) else existing_request['request_data']
                old_template_fields = old_request_data.get('template_fields', {})
                old_template_instances = old_request_data.get('template_instances', [])
                print(f"DEBUG UPDATE-TEMPLATE: Retrieved {len(old_template_instances)} old template instances")
            except:
                pass
        
        # Now execute the update query
        cur.execute(update_query, update_values)
        
        # CHECK: Are there any costed items? If so, protect them - only update general fields
        cur.execute("""
            SELECT id, name, cost_per_item, sell_per_item, total_cost, total_sell,
                   approval_status, negotiation_status, negotiation_reason, negotiation_count, client_feedback
            FROM sales_request_items 
            WHERE request_id = %s 
            AND cost_per_item IS NOT NULL AND cost_per_item > 0
        """, (request_id,))
        costed_items_in_db = cur.fetchall()
        
        has_costed_items = len(costed_items_in_db) > 0
        
        if has_costed_items:
            # Items are costed - DO NOT delete/re-insert items. Only general fields were updated above.
            print(f"DEBUG UPDATE-TEMPLATE: {len(costed_items_in_db)} costed items found - SKIPPING item deletion/re-insertion to preserve costs")
            
            # Still update template instances data (metadata only, not items)
            try:
                cur.execute("DELETE FROM sales_request_template_instances WHERE request_id = %s", (request_id,))
                if template_instances:
                    for idx, instance in enumerate(template_instances):
                        cur.execute("""
                            INSERT INTO sales_request_template_instances 
                            (request_id, template_id, request_type, instance_order, template_data)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (
                            request_id,
                            instance.get('template_id'),
                            instance.get('request_type'),
                            idx,
                            json.dumps(instance.get('fields', {}))
                        ))
            except Exception as inst_err:
                print(f"DEBUG UPDATE-TEMPLATE: Template instance update skipped: {inst_err}")
            
            items_count = len(costed_items_in_db)
            
            conn.commit()
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'General request info updated. {len(costed_items_in_db)} costed item(s) preserved unchanged.',
                'items_count': items_count,
                'costed_items_preserved': True
            })
        
        # NO costed items - safe to delete and re-insert
        # NEW: Delete existing template instances
        try:
            cur.execute("DELETE FROM sales_request_template_instances WHERE request_id = %s", (request_id,))
            print(f"DEBUG UPDATE-TEMPLATE: Deleted existing template instances for request {request_id}")
        except Exception as inst_del_error:
            print(f"DEBUG UPDATE-TEMPLATE: Could not delete template instances (table may not exist): {inst_del_error}")
        
        # Delete existing items (we'll re-insert all items from template_instances)
        cur.execute("DELETE FROM sales_request_items WHERE request_id = %s", (request_id,))
        print(f"DEBUG UPDATE-TEMPLATE: Deleted existing items for request {request_id}")
        
        # NEW: Insert template instances and their items
        items_count = 0
        if template_instances:
            print(f"DEBUG UPDATE-TEMPLATE: Inserting {len(template_instances)} template instances for request {request_id}")
            for idx, instance in enumerate(template_instances):
                try:
                    instance_id = instance.get('instance_id')
                    template_id = instance.get('template_id')
                    instance_request_type = instance.get('request_type')
                    fields = instance.get('fields', {})
                    instance_items = instance.get('items', [])
                    
                    # Insert into sales_request_template_instances table
                    cur.execute("""
                        INSERT INTO sales_request_template_instances 
                        (request_id, template_id, request_type, instance_order, template_data)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        request_id,
                        template_id,
                        instance_request_type,
                        idx,  # Use index as order
                        json.dumps(fields)
                    ))
                    print(f"DEBUG UPDATE-TEMPLATE: ✓ Inserted instance {instance_id} (Template {template_id}, Type: {instance_request_type})")
                    
                    # NEW: Insert items for this instance with request_type
                    for item in instance_items:
                        item_name = item.get('name', '')
                        item_qty = float(item.get('quantity', 1))
                        item_unit = item.get('unit', 'pcs')
                        item_desc = item.get('comment', '') or item.get('description', '')
                        item_request_type = item.get('request_type', instance_request_type)
                        
                        # Get new fields: sell_type, rental_days, dimension_calc, include_days_in_calc, include_qty_in_calc
                        item_sell_type = item.get('sell_type', 'rent')
                        item_rental_days = int(item.get('rental_days', 1)) if item.get('rental_days') else 1
                        item_dimension_calc = item.get('dimension_calc', None)
                        item_include_days = 1 if item.get('include_days_in_calc', True) else 0
                        item_include_qty = 1 if item.get('include_qty_in_calc', True) else 0
                        
                        # Collect dimensions in attributes JSON
                        attributes = {}
                        if item.get('width'):
                            attributes['width'] = float(item.get('width'))
                        if item.get('height'):
                            attributes['height'] = float(item.get('height'))
                        if item.get('depth'):
                            attributes['depth'] = float(item.get('depth'))
                        
                        if item_name:
                            try:
                                cur.execute("""
                                    INSERT INTO sales_request_items (request_id, request_type, name, description, qty, unit, sell_type, rental_days, dimension_calc, include_days_in_calc, include_qty_in_calc, attributes)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """, (
                                    request_id,
                                    item_request_type,
                                    item_name,
                                    item_desc,
                                    item_qty,
                                    item_unit,
                                    item_sell_type,
                                    item_rental_days,
                                    item_dimension_calc if item_dimension_calc else None,
                                    item_include_days,
                                    item_include_qty,
                                    json.dumps(attributes) if attributes else None
                                ))
                                items_count += 1
                                print(f"DEBUG UPDATE-TEMPLATE: ✓ Inserted item '{item_name}' for request type '{item_request_type}' with sell_type={item_sell_type}, rental_days={item_rental_days}, include_days={item_include_days}, dimension_calc={item_dimension_calc}")
                                
                                # Save item to catalog (auto-save for future use)
                                # Unique key: name + unit + width + height + depth
                                save_item_to_catalog_internal(
                                    name=item_name,
                                    unit=item_unit,
                                    width=attributes.get('width'),
                                    height=attributes.get('height'),
                                    depth=attributes.get('depth'),
                                    dimension_calc=item_dimension_calc,
                                    description=item_desc,
                                    conn=conn,
                                    cur=cur
                                )
                            except Exception as item_error:
                                # If request_type column doesn't exist, fall back to old structure
                                if "Unknown column 'request_type'" in str(item_error):
                                    cur.execute("""
                                        INSERT INTO sales_request_items (request_id, name, description, qty, unit, sell_type, rental_days, dimension_calc, attributes)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    """, (
                                        request_id,
                                        item_name,
                                        item_desc,
                                        item_qty,
                                        item_unit,
                                        item_sell_type,
                                        item_rental_days,
                                        item_dimension_calc if item_dimension_calc else None,
                                        json.dumps(attributes) if attributes else None
                                    ))
                                    items_count += 1
                                    print(f"DEBUG UPDATE-TEMPLATE: ✓ Inserted item '{item_name}' (without request_type column) with {len(attributes)} dimensions")
                                else:
                                    raise item_error
                    
                except Exception as inst_error:
                    # If table doesn't exist yet, log but don't fail the request
                    print(f"DEBUG UPDATE-TEMPLATE: Warning - Could not insert template instance: {inst_error}")
                    print(f"DEBUG UPDATE-TEMPLATE: This is normal if sales_request_template_instances table hasn't been created yet")
        
        # LEGACY SUPPORT: Handle old items format if no template_instances
        elif data.get('items'):
            # Get list of costed items (items that cannot be modified)
            cur.execute("""
                SELECT id, name, cost_per_item 
                FROM sales_request_items 
                WHERE request_id = %s 
                AND cost_per_item IS NOT NULL 
                AND cost_per_item > 0
            """, (request_id,))
            costed_items = cur.fetchall()
            costed_items_dict = {item['name']: item for item in costed_items}
            
            if costed_items:
                print(f"DEBUG: Found {len(costed_items)} costed items that need protection:")
                for item in costed_items:
                    print(f"  - {item['name']} (cost: {item['cost_per_item']})")
            
            # Check if any costed items are missing from the update (being removed/modified)
            new_item_names = set([item.get('name', '') for item in data['items']])
            costed_item_names = set(costed_items_dict.keys())
            
            # Costed items that are missing from the update = attempt to remove them
            missing_costed_items = costed_item_names - new_item_names
            
            if missing_costed_items:
                # User is trying to remove costed items - block this
                cur.close()
                conn.close()
                
                error_message = f"Cannot remove costed item(s): {', '.join(missing_costed_items)}"
                if len(missing_costed_items) == 1:
                    error_message = f"Cannot remove item '{list(missing_costed_items)[0]}' - it has been costed by operations"
                else:
                    error_message = f"Cannot remove {len(missing_costed_items)} costed items: {', '.join(missing_costed_items)}"
                
                print(f"DEBUG: Blocked attempt to remove costed items: {missing_costed_items}")
                
                return jsonify({
                    'success': False,
                    'error': error_message,
                    'costed_items': list(missing_costed_items)
                }), 200
            
            # Check if user is trying to MODIFY any costed items (change quantity, description, etc.)
            modified_costed_items = []
            for item in data['items']:
                item_name = item.get('name', '')
                if item_name in costed_items_dict:
                    # This is a costed item - check if it's being modified
                    costed_item = costed_items_dict[item_name]
                    
                    # Get old item data from database
                    cur.execute("SELECT * FROM sales_request_items WHERE id = %s", (costed_item['id'],))
                    old_item = cur.fetchone()
                    
                    if old_item:
                        # Compare attributes
                        old_qty = float(old_item.get('qty', 0))
                        new_qty = float(item.get('quantity', 0))
                        
                        old_desc = old_item.get('description', '') or ''
                        new_desc = item.get('comment', '') or item.get('description', '') or ''
                        
                        old_unit = old_item.get('unit', 'pcs')
                        new_unit = item.get('unit', 'pcs')
                        
                        # Parse old attributes
                        old_attrs = json.loads(old_item.get('attributes', '{}')) if old_item.get('attributes') else {}
                        new_attrs = {}
                        if item.get('width'):
                            new_attrs['width'] = float(item.get('width'))
                        if item.get('height'):
                            new_attrs['height'] = float(item.get('height'))
                        if item.get('depth'):
                            new_attrs['depth'] = float(item.get('depth'))
                        
                        # Check if any attribute changed
                        if (old_qty != new_qty or 
                            old_desc.strip() != new_desc.strip() or 
                            old_unit != new_unit or 
                            old_attrs != new_attrs):
                            
                            modified_costed_items.append(item_name)
                            print(f"DEBUG: Detected modification attempt on costed item '{item_name}'")
                            print(f"  - Qty: {old_qty} -> {new_qty}")
                            print(f"  - Desc: '{old_desc}' -> '{new_desc}'")
                            print(f"  - Unit: {old_unit} -> {new_unit}")
                            print(f"  - Attrs: {old_attrs} -> {new_attrs}")
            
            if modified_costed_items:
                # User is trying to modify costed items - block this
                cur.close()
                conn.close()
                
                error_message = f"Cannot modify costed item(s): {', '.join(modified_costed_items)}"
                if len(modified_costed_items) == 1:
                    error_message = f"Cannot modify item '{modified_costed_items[0]}' - it has been costed by operations and cannot be changed"
                else:
                    error_message = f"Cannot modify {len(modified_costed_items)} costed items: {', '.join(modified_costed_items)}"
                
                print(f"DEBUG: Blocked attempt to modify costed items: {modified_costed_items}")
                
                return jsonify({
                    'success': False,
                    'error': error_message,
                    'costed_items': modified_costed_items
                }), 200
            
            # If we reach here, all costed items are still in the update list
            # Delete ONLY non-costed items (preserve costed items)
            if costed_items:
                costed_ids = [item['id'] for item in costed_items]
                placeholders = ','.join(['%s'] * len(costed_ids))
                cur.execute(f"""
                    DELETE FROM sales_request_items 
                    WHERE request_id = %s 
                    AND id NOT IN ({placeholders})
                """, [request_id] + costed_ids)
                print(f"DEBUG: Deleted non-costed items, preserved {len(costed_items)} costed items")
            else:
                # No costed items, delete all
                cur.execute("DELETE FROM sales_request_items WHERE request_id = %s", (request_id,))
                print(f"DEBUG: No costed items - deleted all items for fresh insert")
            
            # Process new items from the update
            items_count = 0
            for item in data['items']:
                item_name = item.get('name', '')
                item_qty = float(item.get('quantity', 1))
                item_desc = item.get('comment', '') or item.get('description', '')
                item_unit = item.get('unit', 'pcs')
                
                # Check if this item is costed (skip inserting, it's already preserved)
                if item_name in costed_items_dict:
                    items_count += 1  # Count the preserved item
                    print(f"DEBUG: Skipping insert for costed item '{item_name}' - already preserved in database")
                    continue
                
                # This item is NOT costed - insert it
                # Collect measurements in attributes JSON
                attributes = {}
                if item.get('width'):
                    attributes['width'] = float(item.get('width'))
                if item.get('height'):
                    attributes['height'] = float(item.get('height'))
                if item.get('depth'):
                    attributes['depth'] = float(item.get('depth'))
                
                if item_name:
                    cur.execute("""
                        INSERT INTO sales_request_items (
                            request_id, name, description, qty, unit, attributes
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        request_id,
                        item_name,
                        item_desc,
                        item_qty,
                        item_unit,
                        json.dumps(attributes) if attributes else None
                    ))
                    item_id = cur.lastrowid
                    items_count += 1
                    print(f"DEBUG: Inserted item '{item_name}'")
                    
                    # Handle image uploads for this item
                    image_files = item.get('images', [])
                    if image_files and len(image_files) > 0:
                            print(f"DEBUG: Processing {len(image_files)} images for item {item_id}")
                            
                            # Ensure uploads/items directory exists
                            upload_dir = os.path.join(os.getcwd(), 'uploads', 'items')
                            os.makedirs(upload_dir, exist_ok=True)
                            
                            for img_index, img_file in enumerate(image_files):
                                if img_file and img_file.filename:
                                    # Generate unique filename
                                    timestamp = int(time.time())
                                    safe_filename = secure_filename(img_file.filename)
                                    unique_filename = f"req{request_id}_item{item_id}_{timestamp}_{img_index}_{safe_filename}"
                                    file_path = os.path.join(upload_dir, unique_filename)
                                    
                                    # Save file to disk
                                    img_file.save(file_path)
                                    file_size = os.path.getsize(file_path)
                                    
                                    print(f"DEBUG: Saved image to {file_path} (size: {file_size} bytes)")
                                    
                                    # Save image record to database
                                    cur.execute("""
                                        INSERT INTO sales_request_item_images 
                                        (item_id, request_id, image_path, image_name, image_size, display_order, uploaded_by)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    """, (
                                        item_id,
                                        request_id,
                                        f'uploads/items/{unique_filename}',  # Relative path for serving
                                        img_file.filename,
                                        file_size,
                                        img_index,
                                        session.get('username', 'Unknown')
                                    ))
                                    
                                    print(f"DEBUG: Saved image record for item {item_id}, image {img_index}")
                    
                    # Handle catalog image path (when item selected from catalog has existing image)
                    catalog_image_path = item.get('catalog_image_path', '')
                    if catalog_image_path and catalog_image_path.strip():
                        catalog_image_path = catalog_image_path.strip()
                        print(f"DEBUG: Processing catalog image for item {item_id}: {catalog_image_path}")
                        
                        # Check if this image path exists in filesystem
                        full_image_path = os.path.join(os.getcwd(), catalog_image_path.lstrip('/'))
                        if os.path.exists(full_image_path):
                            file_size = os.path.getsize(full_image_path)
                            image_name = os.path.basename(catalog_image_path)
                            
                            # Insert reference to existing catalog image
                            cur.execute("""
                                INSERT INTO sales_request_item_images 
                                (item_id, request_id, image_path, image_name, image_size, display_order, uploaded_by)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (
                                item_id,
                                request_id,
                                catalog_image_path.lstrip('/'),  # Store relative path
                                image_name,
                                file_size,
                                0,  # First image from catalog
                                session.get('username', 'Unknown')
                            ))
                            print(f"DEBUG: Saved catalog image reference for item {item_id}: {catalog_image_path}")
                        else:
                            print(f"DEBUG: Catalog image not found on disk: {full_image_path}")
        
        # Update items count
        print(f"DEBUG UPDATE-TEMPLATE: Total items inserted: {items_count}")
        if items_count > 0:
            cur.execute("UPDATE sales_request SET items_count = %s WHERE id = %s", 
                       (items_count, request_id))
            print(f"DEBUG UPDATE-TEMPLATE: Updated items_count to {items_count} for request {request_id}")
        else:
            print(f"DEBUG UPDATE-TEMPLATE: No items to update (items_count = 0) for request {request_id}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Log the update with SMART field-level change detection - ONLY log actual changes
        # NOTE: old_items_list and old_template_fields were retrieved BEFORE deletion above
        try:
            username = (session.get('name') or session.get('username') or 'Unknown')
            changes_logged = 0
            
            # 1. CLIENT CHANGE - Only if actually different
            if data.get('client_id') and str(existing_request.get('client_id')) != str(data.get('client_id')):
                conn2, cur2 = connection()
                cur2.execute("SELECT client_name FROM client WHERE id = %s", (existing_request.get('client_id'),))
                old_client = cur2.fetchone()
                cur2.execute("SELECT client_name FROM client WHERE id = %s", (data['client_id'],))
                new_client = cur2.fetchone()
                cur2.close()
                conn2.close()
                
                old_client_name = old_client['client_name'] if old_client else 'Unknown'
                new_client_name = new_client['client_name'] if new_client else 'Unknown'
                

                log_request_change(
                    request_id=request_id,
                    action_type='UPDATE',
                    action_by=username,
                    field_name='client_id',
                    old_value=f"{existing_request.get('client_id')} ({old_client_name})",
                    new_value=f"{data['client_id']} ({new_client_name})",
                    change_description=f"Client changed from '{old_client_name}' to '{new_client_name}'"
                )
            
            # 2. TITLE CHANGE - Only if actually different (with trimming)
            if data.get('title') and existing_request.get('title', '').strip() != data['title'].strip():
                log_request_change(
                    request_id=request_id,
                    action_type='UPDATE',
                    action_by=username,
                    field_name='title',
                    old_value=existing_request.get('title'),
                    new_value=data['title'],
                    change_description=f"Title updated"
                )
                changes_logged += 1
            
            # 3. DESCRIPTION CHANGE - Only if actually different  
            if existing_request.get('description', '').strip() != data.get('description', '').strip():
                log_request_change(
                    request_id=request_id,
                    action_type='UPDATE',
                    action_by=username,
                    field_name='description',
                    old_value=existing_request.get('description'),
                    new_value=data.get('description', ''),
                    change_description=f"Description updated"
                )
                changes_logged += 1
            
            # 4. DATE CHANGES - Only if actually different
            old_start = existing_request.get('start_date').strftime('%Y-%m-%d') if existing_request.get('start_date') else None
            old_end = existing_request.get('end_date').strftime('%Y-%m-%d') if existing_request.get('end_date') else None
            
            if data.get('start_date') and old_start != data['start_date']:
                log_request_change(
                    request_id=request_id,
                    action_type='UPDATE',
                    action_by=username,
                    field_name='start_date',
                    old_value=old_start,
                    new_value=data['start_date'],
                    change_description=f"Start date changed from '{old_start}' to '{data['start_date']}'"
                )
                changes_logged += 1
            
            if data.get('end_date') and old_end != data['end_date']:
                log_request_change(
                    request_id=request_id,
                    action_type='UPDATE',
                    action_by=username,
                    field_name='end_date',
                    old_value=old_end,
                    new_value=data['end_date'],
                    change_description=f"End date changed from '{old_end}' to '{data['end_date']}'"
                )
                changes_logged += 1
            
            # 5. REQUEST TYPE CHANGES - Track additions and removals
            old_request_types_str = existing_request.get('request_type', '')
            new_request_types = data.get('request_types', [])
            new_request_types_str = ','.join(new_request_types) if isinstance(new_request_types, list) else str(new_request_types)
            
            old_request_types = set([rt.strip() for rt in old_request_types_str.split(',') if rt.strip()])
            new_request_types_set = set([rt.strip() for rt in new_request_types]) if isinstance(new_request_types, list) else set([rt.strip() for rt in new_request_types_str.split(',') if rt.strip()])
            
            added_types = new_request_types_set - old_request_types
            removed_types = old_request_types - new_request_types_set
            
            if added_types:
                for req_type in added_types:
                    log_request_change(
                        request_id=request_id,
                        action_type='UPDATE',
                        action_by=username,
                        field_name='request_type',
                        old_value=None,
                        new_value=req_type,
                        change_description=f"Added request type: {req_type}"
                    )
                    changes_logged += 1
            
            if removed_types:
                for req_type in removed_types:
                    log_request_change(
                        request_id=request_id,
                        action_type='UPDATE',
                        action_by=username,
                        field_name='request_type',
                        old_value=req_type,
                        new_value=None,
                        change_description=f"Removed request type: {req_type}"
                    )
                    changes_logged += 1
            
            # 6. ITEMS TRACKING - Smart comparison with field-level granularity
            # NEW: Support both legacy items and template_instances structure
            items_to_check = []
            if template_instances:
                # Extract items from template instances
                for instance in template_instances:
                    instance_items = instance.get('items', [])
                    items_to_check.extend(instance_items)
                print(f"DEBUG LOGGING: Using template_instances structure - found {len(items_to_check)} items across {len(template_instances)} instances")
            elif data.get('items'):
                # Legacy structure
                items_to_check = data['items']
                print(f"DEBUG LOGGING: Using legacy items structure - found {len(items_to_check)} items")
            
            if items_to_check:
                # Use the old items we fetched BEFORE deleting
                old_items = old_items_list  # Already fetched before DELETE (line 7757)
                
                print(f"DEBUG LOGGING: Found {len(old_items)} old items from database")
                
                items_data = items_to_check
                print(f"DEBUG LOGGING: Found {len(items_data)} new items to compare")
                
                # Create lookup dictionaries for comparison
                old_items_dict = {item['name']: item for item in old_items}
                new_items_dict = {item.get('name', ''): item for item in items_data if item.get('name')}
                
                print(f"DEBUG LOGGING: Old items: {list(old_items_dict.keys())}")
                print(f"DEBUG LOGGING: New items: {list(new_items_dict.keys())}")
                
                # Track added items
                for item_name, item_data in new_items_dict.items():
                    if item_name not in old_items_dict:
                        qty = item_data.get('quantity', 1)
                        log_request_change(
                            request_id=request_id,
                            action_type='UPDATE',
                            action_by=username,
                            field_name='items',
                            old_value=None,
                            new_value=f"{item_name} (Qty: {qty})",
                            change_description=f"Added new item: {item_name} (Quantity: {qty})"
                        )
                        changes_logged += 1
                
                # Track removed items
                for item_name, old_item in old_items_dict.items():
                    if item_name not in new_items_dict:
                        old_qty = old_item.get('qty', 0)
                        log_request_change(
                            request_id=request_id,
                            action_type='UPDATE',
                            action_by=username,
                            field_name='items',
                            old_value=f"{item_name} (Qty: {old_qty})",
                            new_value=None,
                            change_description=f"Removed item: {item_name} (was Quantity: {old_qty})"
                        )
                        changes_logged += 1
                
                # Track modified items - SMART field-by-field comparison
                for item_name in set(old_items_dict.keys()) & set(new_items_dict.keys()):
                    old_item = old_items_dict[item_name]
                    new_item = new_items_dict[item_name]
                    
                    print(f"DEBUG LOGGING: Checking item '{item_name}'")
                    print(f"DEBUG LOGGING: Old item data: {old_item}")
                    print(f"DEBUG LOGGING: New item data: {new_item}")
                    
                    # Helper function to safely convert to float
                    def get_float(value):
                        if value is None or value == '':
                            return 0.0
                        try:
                            return float(value)
                        except (ValueError, TypeError):
                            return 0.0
                    
                    # Check quantity changes - use epsilon for float comparison
                    old_qty = get_float(old_item.get('qty', 0))
                    new_qty = get_float(new_item.get('quantity', 0))
                    
                    print(f"DEBUG LOGGING: Quantity comparison - Old: {old_qty}, New: {new_qty}, Diff: {abs(old_qty - new_qty)}")
                    
                    if abs(old_qty - new_qty) > 0.001:  # Only log if actually different
                        log_request_change(
                            request_id=request_id,
                            action_type='UPDATE',
                            action_by=username,
                            field_name='item_quantity',
                            old_value=f"{item_name}: {old_qty}",
                            new_value=f"{item_name}: {new_qty}",
                            change_description=f"Item '{item_name}' quantity changed from {old_qty} to {new_qty}"
                        )
                        changes_logged += 1
                    
                    # Check sell price changes - with epsilon
                    old_sell = get_float(old_item.get('sell_per_item', 0))
                    new_sell = get_float(new_item.get('sell_per_item', 0))
                    
                    if abs(old_sell - new_sell) > 0.01:  # Only log if actually different (0.01 for money)
                        if old_sell == 0 and new_sell > 0:
                            log_request_change(
                                request_id=request_id,
                                action_type='UPDATE',
                                action_by=username,
                                field_name='item_sell_price',
                                old_value=None,
                                new_value=f"{item_name}: EGP {new_sell}",
                                change_description=f"Added sell price for item '{item_name}': EGP {new_sell}"
                            )
                        else:
                            log_request_change(
                                request_id=request_id,
                                action_type='UPDATE',
                                action_by=username,
                                field_name='item_sell_price',
                                old_value=f"{item_name}: EGP {old_sell}",
                                new_value=f"{item_name}: EGP {new_sell}",
                                change_description=f"Item '{item_name}' sell price changed from EGP {old_sell} to EGP {new_sell}"
                            )
                        changes_logged += 1
                    
                    # Check description/comment changes - with trimming
                    old_desc = (old_item.get('description', '') or '').strip()
                    new_desc = (new_item.get('comment', '') or new_item.get('description', '') or '').strip()
                    
                    if old_desc != new_desc:  # Only log if actually different
                        log_request_change(
                            request_id=request_id,
                            action_type='UPDATE',
                            action_by=username,
                            field_name='item_description',
                            old_value=f"{item_name}: {old_desc[:50]}..." if len(old_desc) > 50 else f"{item_name}: {old_desc}",
                            new_value=f"{item_name}: {new_desc[:50]}..." if len(new_desc) > 50 else f"{item_name}: {new_desc}",
                            change_description=f"Updated description for item '{item_name}'"
                        )
                        changes_logged += 1
                    
                    # CRITICAL FIX: Check dimensions changes FIELD BY FIELD - NO DUMMY LOGS!
                    old_attrs = json.loads(old_item.get('attributes', '{}')) if old_item.get('attributes') else {}
                    
                    print(f"DEBUG DIMENSIONS: Item '{item_name}' - Old attributes: {old_attrs}")
                    
                    # Get new dimensions
                    new_width = get_float(new_item.get('width'))
                    new_height = get_float(new_item.get('height'))
                    new_depth = get_float(new_item.get('depth'))
                    
                    print(f"DEBUG DIMENSIONS: Item '{item_name}' - New width={new_width}, height={new_height}, depth={new_depth}")
                    
                    # Get old dimensions
                    old_width = get_float(old_attrs.get('width'))
                    old_height = get_float(old_attrs.get('height'))
                    old_depth = get_float(old_attrs.get('depth'))
                    
                    print(f"DEBUG DIMENSIONS: Item '{item_name}' - Old width={old_width}, height={old_height}, depth={old_depth}")
                    
                    # Compare each dimension individually - ONLY LOG IF ACTUALLY CHANGED
                    if abs(old_width - new_width) > 0.001:
                        print(f"DEBUG DIMENSIONS: Width changed for '{item_name}': {old_width} → {new_width}")
                        log_request_change(
                            request_id=request_id,
                            action_type='UPDATE',
                            action_by=username,
                            field_name=f'item_width',
                            old_value=f"{item_name}: {old_width}",
                            new_value=f"{item_name}: {new_width}",
                            change_description=f"Item '{item_name}' width changed from {old_width} to {new_width}"
                        )
                        changes_logged += 1
                    else:
                        print(f"DEBUG DIMENSIONS: Width unchanged for '{item_name}': {old_width} (diff={abs(old_width - new_width)})")
                    
                    if abs(old_height - new_height) > 0.001:
                        print(f"DEBUG DIMENSIONS: Height changed for '{item_name}': {old_height} → {new_height}")
                        log_request_change(
                            request_id=request_id,
                            action_type='UPDATE',
                            action_by=username,
                            field_name=f'item_height',
                            old_value=f"{item_name}: {old_height}",
                            new_value=f"{item_name}: {new_height}",
                            change_description=f"Item '{item_name}' height changed from {old_height} to {new_height}"
                        )
                        changes_logged += 1
                    else:
                        print(f"DEBUG DIMENSIONS: Height unchanged for '{item_name}': {old_height} (diff={abs(old_height - new_height)})")
                    
                    if abs(old_depth - new_depth) > 0.001:
                        print(f"DEBUG DIMENSIONS: Depth changed for '{item_name}': {old_depth} → {new_depth}")
                        log_request_change(
                            request_id=request_id,
                            action_type='UPDATE',
                            action_by=username,
                            field_name=f'item_depth',
                            old_value=f"{item_name}: {old_depth}",
                            new_value=f"{item_name}: {new_depth}",
                            change_description=f"Item '{item_name}' depth changed from {old_depth} to {new_depth}"
                        )
                        changes_logged += 1
                    else:
                        print(f"DEBUG DIMENSIONS: Depth unchanged for '{item_name}': {old_depth} (diff={abs(old_depth - new_depth)})")
            
            # 7. TEMPLATE FIELDS - Field by field comparison (ONLY actual template fields, not metadata)
            old_request_data = json.loads(existing_request.get('request_data', '{}')) if existing_request.get('request_data') else {}
            old_template_fields_data = old_template_fields  # Use the old_template_fields we fetched earlier (line 7793)
            new_template_fields_data = template_fields
            
            print(f"DEBUG TEMPLATE FIELDS: Comparing old template fields: {old_template_fields_data}")
            print(f"DEBUG TEMPLATE FIELDS: With new template fields: {new_template_fields_data}")
            
            # Define derived/computed fields that should be skipped if their source changes
            # duration and duration_days are computed from event_date, so skip them if event_date changed
            derived_fields = {
                'duration': ['Event_event_date', 'event_date', 'start_date', 'end_date'],
                'duration_days': ['Event_event_date', 'event_date', 'start_date', 'end_date']
            }
            
            # Helper function to format date values for human-readable display
            def format_date_for_log(value):
                """Convert YYYY-MM-DD to DD/MM/YYYY for display"""
                if not value:
                    return value
                try:
                    # Try to parse as date
                    from datetime import datetime
                    if isinstance(value, str) and len(value) == 10 and '-' in value:
                        dt = datetime.strptime(value, '%Y-%m-%d')
                        return dt.strftime('%d/%m/%Y')
                except:
                    pass
                return value
            
            # Helper function to get human-readable field name
            def get_field_display_name(field_key):
                """Convert field_key to human-readable name"""
                # Remove common prefixes
                display = field_key
                for prefix in ['Event_', 'Production_', 'Branding_', 'template_']:
                    if display.startswith(prefix):
                        display = display[len(prefix):]
                        break
                # Convert underscores to spaces and title case
                display = display.replace('_', ' ').title()
                return display
            
            # First pass: detect which fields actually changed
            changed_fields = set()
            all_field_keys = set(old_template_fields_data.keys()) | set(new_template_fields_data.keys())
            for field_key in all_field_keys:
                old_field_val = str(old_template_fields_data.get(field_key, '')).strip()
                new_field_val = str(new_template_fields_data.get(field_key, '')).strip()
                if old_field_val != new_field_val:
                    changed_fields.add(field_key)
            
            print(f"DEBUG TEMPLATE FIELDS: Changed fields detected: {changed_fields}")
            
            # Second pass: log changes, skipping derived fields if their source changed
            for field_key in all_field_keys:
                old_field_val = str(old_template_fields_data.get(field_key, '')).strip()
                new_field_val = str(new_template_fields_data.get(field_key, '')).strip()
                
                print(f"DEBUG TEMPLATE FIELD '{field_key}': old='{old_field_val}' vs new='{new_field_val}' - Equal: {old_field_val == new_field_val}")
                
                if old_field_val != new_field_val:
                    # Check if this is a derived field and its source also changed
                    if field_key in derived_fields:
                        source_fields = derived_fields[field_key]
                        source_changed = any(sf in changed_fields for sf in source_fields)
                        if source_changed:
                            print(f"DEBUG TEMPLATE FIELD: Skipping derived field '{field_key}' because source field also changed")
                            continue
                    
                    # Format date values for human-readable display
                    old_display = format_date_for_log(old_field_val) if old_field_val else '(empty)'
                    new_display = format_date_for_log(new_field_val) if new_field_val else '(empty)'
                    field_display = get_field_display_name(field_key)
                    
                    # Create human-readable change description
                    change_desc = f"{field_display} changed from {old_display} to {new_display}"
                    
                    log_request_change(
                        request_id=request_id,
                        action_type='UPDATE',
                        action_by=username,
                        field_name=f'template_{field_key}',
                        old_value=old_field_val,  # Store original value for data integrity
                        new_value=new_field_val,  # Store original value for data integrity
                        change_description=change_desc
                    )
                    changes_logged += 1
                    print(f"DEBUG TEMPLATE FIELD: Logged change for '{field_key}': {change_desc}")
                else:
                    print(f"DEBUG TEMPLATE FIELD: NO CHANGE for '{field_key}' - skipped logging")
            
            # FINAL SUMMARY - Only log if actual changes occurred
            if changes_logged > 0:
                print(f"DEBUG: Logged {changes_logged} actual field changes for request {request_id}")
                log_request_change(
                    request_id=request_id,
                    action_type='UPDATE',
                    action_by=username,
                    change_description=f"Sales request updated - {changes_logged} field(s) changed"
                )
            else:
                print(f"DEBUG: NO CHANGES DETECTED - No dummy logs created for request {request_id}")
                # Don't create a log entry if nothing actually changed!
                
        except Exception as log_error:
            print(f"DEBUG: Failed to log request update: {log_error}")
            import traceback
            print(f"DEBUG: Logging error traceback: {traceback.format_exc()}")
        
        # Return success response (no costed items were attempted to update)
        return jsonify({
            'success': True,
            'message': 'Request updated successfully'
        })
        
    # A scope refusal is a 403, not a server error.
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating request with template: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales-requests/<int:request_id>/attachments', methods=['POST'])
@perm('sales_request.edit')
def upload_request_attachments(request_id):
    """Upload attachments for a request with proper categorization"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        # Verify request exists and user has access
        conn, cur = connection()
        cur.execute("""
            SELECT sr.request_id FROM sales_request sr
            WHERE sr.request_id = %s AND (sr.user_id = %s OR %s IN (
                SELECT user_id FROM users WHERE role IN ('operations', 'admin')
            ))
        """, (request_id, session['user_id'], session['user_id']))
        
        if not cur.fetchone():
            return jsonify({
                'success': False,
                'error': 'Request not found or access denied'
            }), 404
        
        uploaded_files = []
        
        # Process uploaded files
        for file_key in request.files:
            file = request.files[file_key]
            if file and file.filename:
                # Determine file category based on extension
                filename = secure_filename(file.filename)
                file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
                
                if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
                    category = 'photo'
                elif file_ext in ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'csv']:
                    category = 'sheet'
                else:
                    category = 'other'
                
                # Create directory if it doesn't exist
                upload_dir = f"uploads/sales_requests/{request_id}/{category}s"
                os.makedirs(upload_dir, exist_ok=True)
                
                # Save file with unique name to prevent conflicts
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_filename = f"{timestamp}_{filename}"
                file_path = os.path.join(upload_dir, unique_filename)
                file.save(file_path)
                
                # Store attachment record
                cur.execute("""
                    INSERT INTO request_attachment (
                        request_id, file_name, file_path, file_category, 
                        uploaded_date, uploaded_by
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    request_id, filename, file_path, category,
                    datetime.now(), session['user_id']
                ))
                
                uploaded_files.append({
                    'original_name': filename,
                    'stored_name': unique_filename,
                    'category': category,
                    'path': file_path
                })
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'uploaded_files': uploaded_files,
            'message': f'Uploaded {len(uploaded_files)} files successfully'
        })
        
    except Exception as e:
        print(f"Error uploading attachments: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# ITEM CATALOG API ENDPOINTS
# ============================================================================

def save_item_to_catalog_internal(name, unit='pcs', width=None, height=None, depth=None, dimension_calc=None, image_path=None, description='', conn=None, cur=None):
    """
    Internal helper function to save an item to the catalog.
    Checks for uniqueness based on: name + unit + width + height + depth
    If duplicate exists, just updates usage count and dimension_calc/image_path (if provided).
    
    Returns: (item_id, is_new)
    """
    should_close = False
    if conn is None or cur is None:
        conn, cur = connection()
        should_close = True
    
    try:
        # Normalize values
        name = name.strip() if name else ''
        unit = (unit.strip() if unit else 'pcs') or 'pcs'
        width = float(width) if width and str(width).strip() not in ('', 'null', 'None') else None
        height = float(height) if height and str(height).strip() not in ('', 'null', 'None') else None
        depth = float(depth) if depth and str(depth).strip() not in ('', 'null', 'None') else None
        dimension_calc = dimension_calc.strip() if dimension_calc and str(dimension_calc).strip() not in ('', 'null', 'None') else None
        image_path = image_path.strip() if image_path and str(image_path).strip() not in ('', 'null', 'None') else None
        description = description.strip() if description else ''
        
        if not name:
            return None, False
        
        # Check if item already exists (name + unit + dimensions)
        # Using <=> for NULL-safe comparison
        cur.execute("""
            SELECT id, usage_count, dimension_calc FROM item_catalog
            WHERE name = %s AND unit = %s 
            AND (width <=> %s) AND (height <=> %s) AND (depth <=> %s)
        """, (name, unit, width, height, depth))
        
        existing = cur.fetchone()
        
        if existing:
            # Update usage count, last used date, and dimension_calc/image_path if provided
            update_parts = ["usage_count = usage_count + 1", "last_used_at = NOW()"]
            update_params = []
            
            if dimension_calc:
                update_parts.append("dimension_calc = %s")
                update_params.append(dimension_calc)
            
            if image_path:
                update_parts.append("image_path = %s")
                update_params.append(image_path)
            
            update_params.append(existing['id'])
            cur.execute(f"""
                UPDATE item_catalog
                SET {', '.join(update_parts)}
                WHERE id = %s
            """, tuple(update_params))
            
            item_id = existing['id']
            is_new = False
            print(f"DEBUG: Updated catalog item usage: {name} (id={item_id})")
        else:
            # Insert new item
            cur.execute("""
                INSERT INTO item_catalog 
                (name, unit, width, height, depth, dimension_calc, image_path, description, usage_count, last_used_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, NOW())
            """, (name, unit, width, height, depth, dimension_calc, image_path, description))
            
            item_id = cur.lastrowid
            is_new = True
            print(f"DEBUG: Created new catalog item: {name} (id={item_id})")
        
        # Commit if we created the connection
        if should_close:
            conn.commit()
        
        return item_id, is_new
        
    except Exception as e:
        print(f"Error saving item to catalog: {str(e)}")
        return None, False
    finally:
        if should_close:
            cur.close()
            conn.close()

@app.route('/api/item-catalog', methods=['GET'])
@perm('catalog.view')
def get_item_catalog():
    """Get all items from catalog, sorted by usage"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        # Get all catalog items, most used first
        cur.execute("""
            SELECT 
                id, name, unit, width, height, depth, dimension_calc, image_path, description,
                usage_count, last_used_at,
                DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') as created_at
            FROM item_catalog
            ORDER BY usage_count DESC, last_used_at DESC, name ASC
        """)
        
        items = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'items': items,
            'count': len(items)
        })
        
    except Exception as e:
        print(f"Error getting item catalog: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/item-catalog/save', methods=['POST'])
@perm('catalog.edit')
def save_item_to_catalog():
    """Save an item to the catalog (insert or update usage count)"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        data = request.get_json()
        
        name = data.get('name', '').strip()
        unit = data.get('unit', 'pcs').strip()
        width = data.get('width')
        height = data.get('height')
        depth = data.get('depth')
        description = data.get('description', '').strip()
        
        if not name:
            return jsonify({
                'success': False,
                'error': 'Item name is required'
            }), 400
        
        # Convert empty strings to None for dimensions
        width = float(width) if width and str(width).strip() != '' else None
        height = float(height) if height and str(height).strip() != '' else None
        depth = float(depth) if depth and str(depth).strip() != '' else None
        
        conn, cur = connection()
        
        # Check if item already exists (name + unit + dimensions)
        cur.execute("""
            SELECT id, usage_count FROM item_catalog
            WHERE name = %s AND unit = %s 
            AND (width <=> %s) AND (height <=> %s) AND (depth <=> %s)
        """, (name, unit, width, height, depth))
        
        existing = cur.fetchone()
        
        if existing:
            # Update usage count and last used date
            cur.execute("""
                UPDATE item_catalog
                SET usage_count = usage_count + 1,
                    last_used_at = NOW(),
                    description = %s
                WHERE id = %s
            """, (description, existing['id']))
            
            item_id = existing['id']
            is_new = False
        else:
            # Insert new item
            cur.execute("""
                INSERT INTO item_catalog 
                (name, unit, width, height, depth, description, usage_count, last_used_at)
                VALUES (%s, %s, %s, %s, %s, %s, 1, NOW())
            """, (name, unit, width, height, depth, description))
            
            item_id = cur.lastrowid
            is_new = True
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'item_id': item_id,
            'is_new': is_new,
            'message': 'Item saved to catalog' if is_new else 'Item usage updated'
        })
        
    except Exception as e:
        print(f"Error saving item to catalog: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/item-catalog/<int:item_id>', methods=['DELETE'])
@perm('catalog.edit')
def delete_catalog_item(item_id):
    """Delete an item from the catalog"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        cur.execute("DELETE FROM item_catalog WHERE id = %s", (item_id,))
        
        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Item not found'
            }), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Item deleted from catalog'
        })
        
    except Exception as e:
        print(f"Error deleting catalog item: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# END ITEM CATALOG API ENDPOINTS
# ============================================================================

# ============================================================================
# INVENTORY ITEM SEARCH API (for Sales Request)
# ============================================================================

@app.route('/api/inventory/search-items', methods=['GET'])
@perm('inventory.view')
def search_inventory_items():
    """
    Search inventory items for sales request item selection.
    Returns items from both regular inventory and credit inventory.
    Groups by unique key: item_name + unit + dimensions
    Shows current stock levels from both sources.
    """
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    
    try:
        conn, cur = connection()
        
        search_term = request.args.get('q', '').strip()
        print(f"DEBUG: search_inventory_items called, search_term='{search_term}'")
        
        # Query to get inventory items with stock info
        # Combines regular stock and credit inventory stock
        query = """
            SELECT 
                ii.id,
                ii.item_code,
                ii.item_name,
                ii.unit_of_measure AS unit,
                ii.description,
                ii.width,
                ii.height,
                ii.depth,
                ii.specifications,
                ii.category,
                ii.quantity_in_stock AS regular_stock,
                ii.average_cost,
                ii.unit_selling_price,
                ii.is_credit_item,
                ii.status,
                -- Get credit inventory stock for this item
                COALESCE(
                    (SELECT SUM(ici.quantity_remaining) 
                     FROM inventory_credit_items ici 
                     WHERE ici.item_id = ii.id AND ici.status = 'active'),
                    0
                ) AS credit_stock,
                -- Get supplier name if it's a credit item
                (SELECT s.supplier_name FROM supplier s 
                 INNER JOIN inventory_credit_items ici ON s.id = ici.supplier_id 
                 WHERE ici.item_id = ii.id AND ici.status = 'active' 
                 LIMIT 1) AS credit_supplier,
                ii.created_at
            FROM inventory_items ii
            WHERE ii.status = 'active'
        """
        
        params = []
        
        if search_term:
            query += """ AND (
                ii.item_name LIKE %s 
                OR ii.item_code LIKE %s 
                OR ii.description LIKE %s
                OR ii.category LIKE %s
            )"""
            search_pattern = f'%{search_term}%'
            params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
        
        query += " ORDER BY ii.item_name ASC, ii.created_at DESC"
        
        cur.execute(query, params)
        items = cur.fetchall()
        
        print(f"DEBUG: Query returned {len(items)} items")
        
        # Process items to add total stock and format for display
        result_items = []
        for item in items:
            total_stock = (item['regular_stock'] or 0) + (item['credit_stock'] or 0)
            
            # Build display dimensions string
            dims = []
            if item['width']: dims.append(f"W:{item['width']}")
            if item['height']: dims.append(f"H:{item['height']}")
            if item['depth']: dims.append(f"D:{item['depth']}")
            dimensions_str = ' × '.join(dims) if dims else None
            
            result_items.append({
                'id': item['id'],
                'item_code': item['item_code'],
                'name': item['item_name'],
                'unit': item['unit'] or 'pcs',
                'description': item['description'],
                'width': float(item['width']) if item['width'] else None,
                'height': float(item['height']) if item['height'] else None,
                'depth': float(item['depth']) if item['depth'] else None,
                'dimensions_str': dimensions_str,
                'specifications': item['specifications'],
                'category': item['category'],
                'regular_stock': int(item['regular_stock'] or 0),
                'credit_stock': float(item['credit_stock'] or 0),
                'total_stock': total_stock,
                'average_cost': float(item['average_cost']) if item['average_cost'] else 0,
                'selling_price': float(item['unit_selling_price']) if item['unit_selling_price'] else 0,
                'is_credit_item': bool(item['is_credit_item']),
                'credit_supplier': item['credit_supplier'],
                'status': item['status']
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'items': result_items,
            'count': len(result_items)
        })
        
    except Exception as e:
        print(f"Error searching inventory items: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# END INVENTORY ITEM SEARCH API
# ============================================================================

# ============================================================================
# CLIENT APPROVAL API ENDPOINTS
# ============================================================================

@app.route('/client_approval', methods=['GET'])
@perm('client_approval.view')
def client_approval_page():
    """Render client approval management page"""
    return render_template('client_approval.html')

@app.route('/api/client-approval/items', methods=['GET'])
@perm('client_approval.view')
def get_client_approval_items():
    """Get all items for client approval with filters"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Get filter parameters
        status_filter = request.args.get('status', '')
        client_filter = request.args.get('client', '')
        date_range = request.args.get('date_range', '')
        
        # Build base query - Get dimensions from JSON attributes or item_catalog via foreign key
        # Using proper foreign key relationship (item_catalog_id) to avoid duplicates
        # IMPORTANT: Return total_cost and total_sell (pre-calculated with formula)
        query = """
            SELECT 
                i.id,
                i.request_id,
                i.name as item_name,
                i.description,
                i.qty,
                i.unit,
                i.sell_type,
                i.rental_days,
                i.dimension_calc,
                i.include_days_in_calc,
                i.include_qty_in_calc,
                COALESCE(
                    JSON_UNQUOTE(JSON_EXTRACT(i.attributes, '$.width')),
                    ic.width
                ) as width,
                COALESCE(
                    JSON_UNQUOTE(JSON_EXTRACT(i.attributes, '$.height')),
                    ic.height
                ) as height,
                COALESCE(
                    JSON_UNQUOTE(JSON_EXTRACT(i.attributes, '$.depth')),
                    ic.depth
                ) as depth,
                i.cost_per_item,
                i.sell_per_item,
                i.total_cost,
                i.total_sell,
                i.negotiation_count,
                i.approval_status,
                i.submitted_for_approval_date,
                i.submitted_by,
                i.client_approval_date,
                i.client_feedback,
                sr.client_id,
                c.client_name,
                sr.sales_added_date,
                u.name as submitted_by_name
            FROM sales_request_items i
            INNER JOIN sales_request sr ON i.request_id = sr.id
            LEFT JOIN item_catalog ic ON i.item_catalog_id = ic.id
            LEFT JOIN client c ON sr.client_id = c.id
            LEFT JOIN user u ON i.submitted_by = u.id
            WHERE 1=1
        """

        # Row-level scope on the owning request, applied before any user filter.
        scope_sql, params = scope_clause('client_approval.view', 'sr.owner_user_id')
        query += scope_sql

        # Apply status filter
        if status_filter == 'pending':
            query += " AND (i.cost_per_item IS NULL OR i.sell_per_item IS NULL)"
        elif status_filter == 'priced':
            query += " AND i.cost_per_item IS NOT NULL AND i.sell_per_item IS NOT NULL AND (i.approval_status = 'pending' OR i.approval_status IS NULL)"
        elif status_filter == 'approved':
            query += " AND i.approval_status = 'approved'"
        elif status_filter == 'rejected':
            query += " AND i.approval_status = 'rejected'"
        elif status_filter == 'pending_negotiation':
            query += " AND i.approval_status = 'pending_negotiation'"
        
        # Apply client filter
        if client_filter:
            query += " AND sr.client_id = %s"
            params.append(client_filter)
        
        # Apply date range filter
        if date_range == 'today':
            query += " AND DATE(sr.sales_added_date) = CURDATE()"
        elif date_range == 'week':
            query += " AND sr.sales_added_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        elif date_range == 'month':
            query += " AND sr.sales_added_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
        
        query += " ORDER BY i.id DESC"
        
        cur.execute(query, params)
        items = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'items': items
        })
        
    except Exception as e:
        print(f"Error fetching client approval items: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/client-approval/statistics', methods=['GET'])
@perm('client_approval.view')
def get_client_approval_statistics():
    """Get client approval statistics"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Get counts for different statuses
        cur.execute("""
            SELECT 
                COUNT(CASE WHEN (cost_per_item IS NULL OR cost_per_item = 0 
                                 OR sell_per_item IS NULL OR sell_per_item = 0) THEN 1 END) as pending_pricing,
                COUNT(CASE WHEN cost_per_item IS NOT NULL AND cost_per_item > 0 
                           AND sell_per_item IS NOT NULL AND sell_per_item > 0
                           AND (approval_status IS NULL OR approval_status = '' 
                                OR approval_status = 'pending') THEN 1 END) as ready_to_submit,
                COUNT(CASE WHEN approval_status = 'approved' THEN 1 END) as approved,
                COUNT(CASE WHEN approval_status = 'rejected' THEN 1 END) as rejected,
                COUNT(CASE WHEN approval_status = 'pending_negotiation' THEN 1 END) as in_negotiation
            FROM sales_request_items
        """)
        
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'pending_pricing': result['pending_pricing'],
                'ready_to_submit': result['ready_to_submit'],
                'approved': result['approved'],
                'rejected': result['rejected'],
                'in_negotiation': result['in_negotiation']
            }
        })
        
    except Exception as e:
        print(f"Error fetching client approval statistics: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/client-approval/items/<int:item_id>', methods=['GET'])
@perm('client_approval.view')
def get_client_approval_item_details(item_id):
    """Get detailed information about a specific item"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        cur.execute("""
            SELECT 
                i.*,
                sr.client_id,
                c.client_name,
                u.name as submitted_by_name
            FROM sales_request_items i
            INNER JOIN sales_request sr ON i.request_id = sr.id
            LEFT JOIN client c ON sr.client_id = c.id
            LEFT JOIN user u ON i.submitted_by = u.id
            WHERE i.id = %s
        """, (item_id,))
        
        item = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if not item:
            return jsonify({
                'success': False,
                'error': 'Item not found'
            }), 404
        
        return jsonify({
            'success': True,
            'item': item
        })
        
    except Exception as e:
        print(f"Error fetching item details: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/client-approval/items/<int:item_id>/submit', methods=['POST'])
@perm('client_approval.submit')
def submit_item_for_approval(item_id):
    """Submit an item for client approval"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        notes = data.get('notes', '')
        user_id = session.get('user_id')
        user_name = session.get('name', 'Unknown')
        
        conn, cur = connection()
        
        # First, get item details and verify pricing is set
        cur.execute("""
            SELECT i.*, sr.client_id, c.client_name
            FROM sales_request_items i
            INNER JOIN sales_request sr ON i.request_id = sr.id
            LEFT JOIN client c ON sr.client_id = c.id
            WHERE i.id = %s
        """, (item_id,))
        
        item = cur.fetchone()
        
        if not item:
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Item not found'
            }), 404
        
        # Check if pricing is set
        if not item['cost_per_item'] or not item['sell_per_item']:
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Cannot submit item without cost and selling price'
            }), 400
        
        # Update item status to pending (ready for client review)
        cur.execute("""
            UPDATE sales_request_items
            SET approval_status = 'pending',
                submitted_for_approval_date = NOW(),
                submitted_by = %s
            WHERE id = %s
        """, (user_id, item_id))
        
        # Log the approval action
        cur.execute("""
            INSERT INTO item_client_approval_log
            (item_id, request_id, action_type, action_by, previous_status, new_status, notes, cost_per_item, sell_per_item)
            VALUES (%s, %s, 'submitted', %s, %s, 'pending', %s, %s, %s)
        """, (
            item_id,
            item['request_id'],
            user_id,
            item['approval_status'] or 'pending',
            notes,
            item['cost_per_item'],
            item['sell_per_item']
        ))
        
        conn.commit()
        
        # Log the change in the main change log
        log_item_change(
            request_id=item['request_id'],
            item_id=item_id,
            item_name=item['name'],
            request_type=item.get('request_type', 'General'),
            action_type='submitted_for_approval',
            action_by=user_name,
            change_description=f"Item submitted for client approval. Cost: {item['cost_per_item']}, Sell: {item['sell_per_item']}. Notes: {notes}",
            conn=conn,
            cur=cur
        )
        
        # Update request's overall approval stage
        update_request_approval_stage(item['request_id'], conn, cur)
        
        conn.commit()
        cur.close()
        conn.close()
        
        # TODO: Send notification to client (can be implemented later)
        # send_notification_to_client(item['client_id'], item_id, item['item_name'])
        
        return jsonify({
            'success': True,
            'message': 'Item submitted for client approval'
        })
        
    except Exception as e:
        print(f"Error submitting item for approval: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/client-approval/items/<int:item_id>/history', methods=['GET'])
@perm('client_approval.view')
def get_item_approval_history(item_id):
    """Get approval history for an item"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        cur.execute("""
            SELECT 
                h.*,
                u.name as action_by_name
            FROM item_client_approval_log h
            LEFT JOIN user u ON h.action_by = u.id
            WHERE h.item_id = %s
            ORDER BY h.action_date DESC
        """, (item_id,))
        
        history = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'history': history
        })
        
    except Exception as e:
        print(f"Error fetching approval history: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/client-approval/items/<int:item_id>/approve', methods=['POST'])
@perm('client_approval.decide')
def approve_item(item_id):
    """Approve an item (can be used by admin or when client approves)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        feedback = data.get('feedback', '')
        user_id = session.get('user_id')
        user_name = session.get('name', 'Unknown')
        
        conn, cur = connection()
        
        # Get item details
        cur.execute("""
            SELECT i.*, sr.client_id
            FROM sales_request_items i
            INNER JOIN sales_request sr ON i.request_id = sr.id
            WHERE i.id = %s
        """, (item_id,))
        
        item = cur.fetchone()
        
        if not item:
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Item not found'
            }), 404
        
        # Update item status
        cur.execute("""
            UPDATE sales_request_items
            SET approval_status = 'approved',
                client_approval_date = NOW(),
                client_feedback = %s
            WHERE id = %s
        """, (feedback, item_id))
        
        # Log the approval
        cur.execute("""
            INSERT INTO item_client_approval_log
            (item_id, request_id, action_type, action_by, previous_status, new_status, notes)
            VALUES (%s, %s, 'approved', %s, %s, 'approved', %s)
        """, (
            item_id,
            item['request_id'],
            user_id,
            item['approval_status'] or 'submitted',
            feedback
        ))
        
        # Log in main change log
        log_item_change(
            request_id=item['request_id'],
            item_id=item_id,
            item_name=item['name'],
            request_type=item.get('request_type', 'General'),
            action_type='CLIENT_APPROVED',
            action_by=user_name,
            change_description=f"[Client Approval] Item '{item['name']}' approved by client" + (f". Feedback: {feedback}" if feedback else ""),
            conn=conn,
            cur=cur
        )
        
        # Update request's overall approval stage
        update_request_approval_stage(item['request_id'], conn, cur)
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Item approved successfully'
        })
        
    except Exception as e:
        print(f"Error approving item: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/client-approval/items/<int:item_id>/reject', methods=['POST'])
@perm('client_approval.decide')
def reject_item(item_id):
    """Reject an item"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        feedback = data.get('feedback', '')
        user_id = session.get('user_id')
        user_name = session.get('name', 'Unknown')
        
        conn, cur = connection()
        
        # Get item details
        cur.execute("""
            SELECT i.*, sr.client_id
            FROM sales_request_items i
            INNER JOIN sales_request sr ON i.request_id = sr.id
            WHERE i.id = %s
        """, (item_id,))
        
        item = cur.fetchone()
        
        if not item:
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Item not found'
            }), 404
        
        # Update item status
        cur.execute("""
            UPDATE sales_request_items
            SET approval_status = 'rejected',
                client_approval_date = NOW(),
                client_feedback = %s
            WHERE id = %s
        """, (feedback, item_id))
        
        # Log the rejection
        cur.execute("""
            INSERT INTO item_client_approval_log
            (item_id, request_id, action_type, action_by, previous_status, new_status, notes)
            VALUES (%s, %s, 'rejected', %s, %s, 'rejected', %s)
        """, (
            item_id,
            item['request_id'],
            user_id,
            item['approval_status'] or 'submitted',
            feedback
        ))
        
        # Log in main change log
        log_item_change(
            request_id=item['request_id'],
            item_id=item_id,
            item_name=item['name'],
            request_type=item.get('request_type', 'General'),
            action_type='CLIENT_REJECTED',
            action_by=user_name,
            change_description=f"[Client Approval] Item '{item['name']}' rejected by client. Reason: {feedback}",
            conn=conn,
            cur=cur
        )
        
        # Update request's overall approval stage
        update_request_approval_stage(item['request_id'], conn, cur)
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Item rejected'
        })
        
    except Exception as e:
        print(f"Error rejecting item: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/client-approval/items/<int:item_id>/negotiate', methods=['POST'])
@perm('client_approval.decide')
def negotiate_item_price(item_id):
    """NEW: Create negotiation request with expected price - routes through Sales Head"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        negotiation_reason = data.get('reason', '')
        expected_price = data.get('expected_price')
        user_id = session.get('user_id')
        user_name = session.get('name', 'Unknown')
        
        if not negotiation_reason:
            return jsonify({
                'success': False,
                'error': 'Negotiation reason is required'
            }), 400
        
        if not expected_price or float(expected_price) <= 0:
            return jsonify({
                'success': False,
                'error': 'Valid expected price is required'
            }), 400
        
        conn, cur = connection()
        
        # Get current item details
        cur.execute("""
            SELECT i.*, sr.client_id, sr.title as request_title
            FROM sales_request_items i
            INNER JOIN sales_request sr ON i.request_id = sr.id
            WHERE i.id = %s
        """, (item_id,))
        
        item = cur.fetchone()
        
        if not item:
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Item not found'
            }), 404
        
        # Save current prices to history before negotiation
        cur.execute("""
            INSERT INTO sales_request_item_price_history
            (item_id, request_id, version, cost_per_item, sell_per_item, total_cost, total_sell,
             profit_amount, profit_margin, status, negotiation_reason, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'negotiated', %s, %s)
        """, (
            item_id,
            item['request_id'],
            item.get('negotiation_count', 0) + 1,
            item.get('cost_per_item'),
            item.get('sell_per_item'),
            item.get('total_cost'),
            item.get('total_sell'),
            (float(item.get('total_sell', 0) or 0) - float(item.get('total_cost', 0) or 0)),
            ((float(item.get('total_sell', 0) or 0) - float(item.get('total_cost', 0) or 0)) / float(item.get('total_cost', 1) or 1) * 100) if item.get('total_cost') else 0,
            negotiation_reason,
            user_name
        ))
        
        # Create negotiation request - NEW WORKFLOW
        cur.execute("""
            INSERT INTO negotiation_requests
            (item_id, request_id, client_expected_price, client_reason, status, sales_head_decision)
            VALUES (%s, %s, %s, %s, 'pending_sales_head', 'pending')
        """, (
            item_id,
            item['request_id'],
            float(expected_price),
            negotiation_reason
        ))
        
        negotiation_id = cur.lastrowid
        
        # Create initial log entry
        cur.execute("""
            INSERT INTO negotiation_logs
            (negotiation_id, action, actor_user_id, actor_name, notes, old_price, new_price)
            VALUES (%s, 'negotiation_created', %s, %s, %s, %s, %s)
        """, (
            negotiation_id,
            user_id,
            user_name,
            f"Negotiation created: {negotiation_reason}",
            item.get('sell_per_item'),
            float(expected_price)
        ))
        
        # Update item status - Set to pending_negotiation
        cur.execute("""
            UPDATE sales_request_items
            SET approval_status = 'pending_negotiation',
                negotiation_status = 'pending_negotiation',
                negotiation_reason = %s,
                negotiation_count = COALESCE(negotiation_count, 0) + 1,
                client_approval_date = NOW(),
                client_feedback = CONCAT('Price negotiation requested. Expected price: EGP ', %s, '. Reason: ', %s)
            WHERE id = %s
        """, (negotiation_reason, float(expected_price), negotiation_reason, item_id))
        
        # Log the negotiation request
        cur.execute("""
            INSERT INTO item_client_approval_log
            (item_id, request_id, action_type, action_by, previous_status, new_status, notes)
            VALUES (%s, %s, 'negotiation_requested', %s, %s, 'pending_negotiation', %s)
        """, (
            item_id,
            item['request_id'],
            user_id,
            item['approval_status'] or 'submitted',
            f"Negotiation #{item.get('negotiation_count', 0) + 1}: Expected price EGP {float(expected_price)}, Reason: {negotiation_reason}"
        ))
        
        # Log in main change log
        log_item_change(
            request_id=item['request_id'],
            item_id=item_id,
            item_name=item['name'],
            request_type=item.get('request_type', 'General'),
            action_type='CLIENT_NEGOTIATION',
            action_by=user_name,
            old_data={'cost': item.get('cost_per_item'), 'sell': item.get('sell_per_item')},
            new_data={'status': 'pending_negotiation', 'expected_price': float(expected_price), 'reason': negotiation_reason},
            change_description=f"[Client Approval] Price negotiation requested for '{item['name']}' (#{item.get('negotiation_count', 0) + 1}). Expected price: EGP {float(expected_price)}, Reason: {negotiation_reason}. Pending Sales Head approval.",
            conn=conn,
            cur=cur
        )
        
        # Update request's overall approval stage
        update_request_approval_stage(item['request_id'], conn, cur)
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Negotiation submitted to Sales Head for review.',
            'negotiation_count': item.get('negotiation_count', 0) + 1,
            'negotiation_id': negotiation_id
        })
        
    except Exception as e:
        print(f"Error requesting negotiation: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =============================================================================
# SALES HEAD APPROVAL ROUTES
# =============================================================================

@app.route('/sales-head-approval')
@perm('negotiation.decide_sales_head')
def sales_head_approval_page():
    """Sales Head Approval page - admin role is always allowed by decorator"""
    return render_template('sales_head_approval.html')

@app.route('/api/sales-head/negotiations', methods=['GET'])
@perm('negotiation.decide_sales_head')
def get_sales_head_negotiations():
    """Get all negotiation requests for sales head review"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        status = request.args.get('status', 'pending_sales_head')
        client_id = request.args.get('client_id')
        date_range = request.args.get('date_range', 'all')
        
        conn, cur = connection()
        
        # Build WHERE clause
        where_clauses = []
        params = []
        
        if status:
            where_clauses.append("nr.status = %s")
            params.append(status)
        
        if client_id:
            where_clauses.append("sr.client_id = %s")
            params.append(client_id)
        
        # Date filter
        if date_range == 'today':
            where_clauses.append("DATE(nr.created_at) = CURDATE()")
        elif date_range == 'week':
            where_clauses.append("nr.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)")
        elif date_range == 'month':
            where_clauses.append("nr.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)")
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Get negotiations with item and request details
        query = f"""
            SELECT 
                nr.*,
                sri.name as item_name,
                sri.qty as quantity,
                sri.unit,
                sri.sell_per_item as current_selling_price,
                sri.cost_per_item as current_cost_price,
                sri.negotiation_count,
                sr.id as request_id,
                c.client_name
            FROM negotiation_requests nr
            INNER JOIN sales_request_items sri ON nr.item_id = sri.id
            INNER JOIN sales_request sr ON nr.request_id = sr.id
            LEFT JOIN client c ON sr.client_id = c.id
            WHERE {where_sql}
            ORDER BY nr.created_at DESC
        """
        
        cur.execute(query, params)
        negotiations = cur.fetchall()
        
        # Convert to list of dicts
        result = []
        for neg in negotiations:
            result.append({
                'id': neg['id'],
                'item_id': neg['item_id'],
                'request_id': neg['request_id'],
                'item_name': neg['item_name'],
                'quantity': float(neg['quantity']) if neg['quantity'] else 0,
                'unit': neg['unit'],
                'client_expected_price': float(neg['client_expected_price']) if neg['client_expected_price'] else 0,
                'client_reason': neg['client_reason'],
                'current_selling_price': float(neg['current_selling_price']) if neg['current_selling_price'] else 0,
                'current_cost_price': float(neg['current_cost_price']) if neg['current_cost_price'] else 0,
                'status': neg['status'],
                'destination_team': neg.get('destination_team'),
                'sales_head_decision': neg['sales_head_decision'],
                'sales_head_notes': neg['sales_head_notes'],
                'client_name': neg['client_name'],
                'negotiation_count': neg['negotiation_count'] or 0,
                'created_at': neg['created_at'].strftime('%Y-%m-%d %H:%M:%S') if neg['created_at'] else None
            })
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'negotiations': result
        })
        
    except Exception as e:
        print(f"Error getting negotiations: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales-head/negotiations/statistics', methods=['GET'])
@perm('negotiation.decide_sales_head')
def get_sales_head_statistics():
    """Get statistics for sales head dashboard"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Pending count
        cur.execute("""
            SELECT COUNT(*) as count
            FROM negotiation_requests
            WHERE status = 'pending_sales_head'
        """)
        pending = cur.fetchone()['count']
        
        # Approved today, regardless of what Pricing did afterward
        cur.execute("""
            SELECT COUNT(*) as count
            FROM negotiation_requests
            WHERE sales_head_decision = 'approved'
            AND DATE(sales_head_decision_date) = CURDATE()
        """)
        approved_today = cur.fetchone()['count']
        
        # Declined today
        cur.execute("""
            SELECT COUNT(*) as count
            FROM negotiation_requests
            WHERE status = 'sales_head_declined'
            AND DATE(sales_head_decision_date) = CURDATE()
        """)
        declined_today = cur.fetchone()['count']
        
        # Potential savings (difference between current price and expected price for pending)
        cur.execute("""
            SELECT 
                SUM((sri.sell_per_item - nr.client_expected_price) * sri.qty) as savings
            FROM negotiation_requests nr
            INNER JOIN sales_request_items sri ON nr.item_id = sri.id
            WHERE nr.status = 'pending_sales_head'
            AND sri.sell_per_item IS NOT NULL
        """)
        savings_result = cur.fetchone()
        potential_savings = float(savings_result['savings']) if savings_result['savings'] else 0
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'pending': pending,
                'approved_today': approved_today,
                'declined_today': declined_today,
                'potential_savings': potential_savings
            }
        })
        
    except Exception as e:
        print(f"Error getting statistics: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales-head/negotiations/<int:negotiation_id>/approve', methods=['POST'])
@perm('negotiation.decide_sales_head')
def approve_sales_head_negotiation(negotiation_id):
    """Approve a negotiation and always send it to Pricing for a decision."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        notes = data.get('notes', '')
        user_id = session.get('user_id')
        user_name = session.get('name', 'Sales Head')
        
        conn, cur = connection()
        
        # Get negotiation details
        cur.execute("""
            SELECT nr.*, sri.name as item_name, sri.request_id
            FROM negotiation_requests nr
            INNER JOIN sales_request_items sri ON nr.item_id = sri.id
            WHERE nr.id = %s
        """, (negotiation_id,))
        
        negotiation = cur.fetchone()
        
        if not negotiation:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Negotiation not found'}), 404
        
        if negotiation['status'] != 'pending_sales_head':
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Negotiation already processed'}), 400
        
        new_status = transition(negotiation['status'], 'sales_head', 'approve')
        
        # Update negotiation status
        cur.execute("""
            UPDATE negotiation_requests
            SET status = %s,
                sales_head_decision = 'approved',
                sales_head_notes = %s,
                sales_head_user_id = %s,
                sales_head_decision_date = NOW(),
                destination_team = %s
            WHERE id = %s
        """, (new_status, notes, user_id, 'pricing', negotiation_id))
        
        # Log the approval
        cur.execute("""
            INSERT INTO negotiation_logs
            (negotiation_id, action, actor_user_id, actor_name, notes)
            VALUES (%s, %s, %s, %s, %s)
        """, (negotiation_id, 'sales_head_approved_to_pricing', user_id, user_name, notes or 'Approved by Sales Head. Sent to Re-Pricing for decision.'))

        feedback_msg = ' | Sales Head Approved. Sent to Re-Pricing for review.'
        cur.execute("""
            UPDATE sales_request_items
            SET negotiation_status = 'negotiated',
                client_feedback = CONCAT(COALESCE(client_feedback, ''), %s)
            WHERE id = %s
        """, (feedback_msg, negotiation['item_id']))
        
        # Log in main change log
        log_item_change(
            request_id=negotiation['request_id'],
            item_id=negotiation['item_id'],
            item_name=negotiation['item_name'],
            request_type='Negotiation',
            action_type='SALES_HEAD_APPROVED_TO_PRICING',
            action_by=user_name,
            old_data={'status': 'pending_sales_head'},
            new_data={'status': new_status, 'destination': 'pricing', 'notes': notes},
            change_description=f"[Sales Head] Approved negotiation for '{negotiation['item_name']}'. Sent to Re-Pricing for decision. Expected price: EGP {float(negotiation['client_expected_price'])}",
            conn=conn,
            cur=cur
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Negotiation approved and sent to Re-Pricing'
        })
        
    except Exception as e:
        print(f"Error approving negotiation: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/pricing/negotiations/<int:negotiation_id>/send-to-costing', methods=['POST'])
@perm('negotiation.decide_pricing')
def pricing_send_negotiation_to_costing(negotiation_id):
    """Let Pricing request re-costing before it sets a new selling price."""
    try:
        data = request.get_json() or {}
        notes = data.get('notes', '').strip()
        user_id = session.get('user_id')
        user_name = session.get('name', 'Pricing')
        conn, cur = connection()

        cur.execute("""
            SELECT nr.*, sri.name AS item_name, sri.request_id
            FROM negotiation_requests nr
            INNER JOIN sales_request_items sri ON nr.item_id = sri.id
            WHERE nr.id = %s
        """, (negotiation_id,))
        negotiation = cur.fetchone()

        if not negotiation:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Negotiation not found'}), 404

        try:
            new_status = transition(
                negotiation['status'], 'pricing', 'send_to_costing'
            )
        except InvalidNegotiationTransition as exc:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': str(exc)}), 409

        cur.execute("""
            UPDATE negotiation_requests
            SET status = %s, destination_team = 'costing'
            WHERE id = %s
        """, (new_status, negotiation_id))
        cur.execute("""
            UPDATE sales_request_items
            SET negotiation_status = 'pending_negotiation',
                client_feedback = CONCAT(
                    COALESCE(client_feedback, ''),
                    ' | Re-Pricing requested re-costing first.'
                )
            WHERE id = %s
        """, (negotiation['item_id'],))
        cur.execute("""
            INSERT INTO negotiation_logs
                (negotiation_id, action, actor_user_id, actor_name, notes)
            VALUES (%s, 'pricing_sent_to_costing', %s, %s, %s)
        """, (
            negotiation_id,
            user_id,
            user_name,
            notes or 'Pricing requested updated cost before re-pricing.'
        ))
        log_item_change(
            request_id=negotiation['request_id'],
            item_id=negotiation['item_id'],
            item_name=negotiation['item_name'],
            request_type='Negotiation',
            action_type='PRICING_SENT_TO_RECOSTING',
            action_by=user_name,
            old_data={'status': negotiation['status']},
            new_data={'status': new_status, 'notes': notes},
            change_description=f"[Re-Pricing] Sent '{negotiation['item_name']}' to Operations for re-costing before the selling price decision.",
            conn=conn,
            cur=cur
        )

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            'success': True,
            'message': 'Negotiation sent to Operations for re-costing'
        })
    except Exception as e:
        print(f"Error sending negotiation to re-costing: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pricing/negotiations/<int:negotiation_id>/decline', methods=['POST'])
@perm('negotiation.decide_pricing')
def pricing_decline_negotiation(negotiation_id):
    """Decline a negotiation from Pricing and retain the existing price."""
    try:
        data = request.get_json() or {}
        reason = data.get('reason', '').strip()
        if not reason:
            return jsonify({'success': False, 'error': 'Reason is required'}), 400

        user_id = session.get('user_id')
        user_name = session.get('name', 'Pricing')
        conn, cur = connection()
        cur.execute("""
            SELECT nr.*, sri.name AS item_name, sri.request_id
            FROM negotiation_requests nr
            INNER JOIN sales_request_items sri ON nr.item_id = sri.id
            WHERE nr.id = %s
        """, (negotiation_id,))
        negotiation = cur.fetchone()

        if not negotiation:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Negotiation not found'}), 404

        try:
            new_status = transition(negotiation['status'], 'pricing', 'decline')
        except InvalidNegotiationTransition as exc:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': str(exc)}), 409

        cur.execute("""
            UPDATE negotiation_requests
            SET status = %s, destination_team = 'pricing'
            WHERE id = %s
        """, (new_status, negotiation_id))
        cur.execute("""
            UPDATE sales_request_items
            SET approval_status = 'pending',
                negotiation_status = 'none',
                client_feedback = CONCAT(
                    COALESCE(client_feedback, ''),
                    ' | Re-Pricing Declined: ', %s
                )
            WHERE id = %s
        """, (reason, negotiation['item_id']))
        cur.execute("""
            INSERT INTO negotiation_logs
                (negotiation_id, action, actor_user_id, actor_name, notes)
            VALUES (%s, 'pricing_declined', %s, %s, %s)
        """, (negotiation_id, user_id, user_name, reason))
        log_item_change(
            request_id=negotiation['request_id'],
            item_id=negotiation['item_id'],
            item_name=negotiation['item_name'],
            request_type='Negotiation',
            action_type='PRICING_DECLINED_NEGOTIATION',
            action_by=user_name,
            old_data={'status': negotiation['status']},
            new_data={'status': new_status, 'reason': reason},
            change_description=f"[Re-Pricing] Declined negotiation for '{negotiation['item_name']}'. Existing selling price retained. Reason: {reason}",
            conn=conn,
            cur=cur
        )
        update_request_approval_stage(
            negotiation['request_id'], conn, cur
        )

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            'success': True,
            'message': 'Negotiation declined; existing price returned to Client Approval'
        })
    except Exception as e:
        print(f"Error declining negotiation from Pricing: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sales-head/negotiations/<int:negotiation_id>/decline', methods=['POST'])
@perm('negotiation.decide_sales_head')
def decline_sales_head_negotiation(negotiation_id):
    """Decline negotiation - return to client approval"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        reason = data.get('reason', '')
        user_id = session.get('user_id')
        user_name = session.get('name', 'Sales Head')
        
        if not reason:
            return jsonify({'success': False, 'error': 'Reason is required'}), 400
        
        conn, cur = connection()
        
        # Get negotiation details
        cur.execute("""
            SELECT nr.*, sri.name as item_name, sri.request_id
            FROM negotiation_requests nr
            INNER JOIN sales_request_items sri ON nr.item_id = sri.id
            WHERE nr.id = %s
        """, (negotiation_id,))
        
        negotiation = cur.fetchone()
        
        if not negotiation:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Negotiation not found'}), 404
        
        if negotiation['status'] != 'pending_sales_head':
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Negotiation already processed'}), 400
        
        # Update negotiation status
        cur.execute("""
            UPDATE negotiation_requests
            SET status = 'sales_head_declined',
                sales_head_decision = 'declined',
                sales_head_notes = %s,
                sales_head_user_id = %s,
                sales_head_decision_date = NOW()
            WHERE id = %s
        """, (reason, user_id, negotiation_id))
        
        # Log the decline
        cur.execute("""
            INSERT INTO negotiation_logs
            (negotiation_id, action, actor_user_id, actor_name, notes)
            VALUES (%s, 'sales_head_declined', %s, %s, %s)
        """, (negotiation_id, user_id, user_name, reason))
        
        # Update item status - return to pending client approval
        cur.execute("""
            UPDATE sales_request_items
            SET approval_status = 'pending',
                negotiation_status = 'none',
                client_feedback = CONCAT(COALESCE(client_feedback, ''), ' | Sales Head Declined: ', %s)
            WHERE id = %s
        """, (reason, negotiation['item_id']))
        
        # Log in main change log
        log_item_change(
            request_id=negotiation['request_id'],
            item_id=negotiation['item_id'],
            item_name=negotiation['item_name'],
            request_type='Negotiation',
            action_type='SALES_HEAD_DECLINED',
            action_by=user_name,
            old_data={'status': 'pending_sales_head'},
            new_data={'status': 'declined', 'reason': reason},
            change_description=f"[Sales Head] Declined negotiation for '{negotiation['item_name']}'. Reason: {reason}. Returned to Pending Client Approval.",
            conn=conn,
            cur=cur
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Negotiation declined and returned to Pending Client Approval'
        })
        
    except Exception as e:
        print(f"Error declining negotiation: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/client-approval/items/<int:item_id>/price-history', methods=['GET'])
@perm('client_approval.view')
def get_item_price_history(item_id):
    """Get price history for an item showing all negotiation rounds"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Get price history
        cur.execute("""
            SELECT 
                h.*,
                DATE_FORMAT(h.created_at, '%%Y-%%m-%%d %%H:%%i') as formatted_date
            FROM sales_request_item_price_history h
            WHERE h.item_id = %s
            ORDER BY h.version DESC, h.created_at DESC
        """, (item_id,))
        
        history = cur.fetchall()
        
        # Get current item prices
        cur.execute("""
            SELECT 
                cost_per_item,
                sell_per_item,
                total_cost,
                total_sell,
                negotiation_count,
                approval_status
            FROM sales_request_items
            WHERE id = %s
        """, (item_id,))
        
        current = cur.fetchone()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'history': history,
            'current': current
        })
        
    except Exception as e:
        print(f"Error fetching price history: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sales/requests/<int:request_id>/approval-stage', methods=['GET'])
@perm('sales_request.view')
def get_request_approval_stage(request_id):
    """Get detailed approval stage information for a request"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Get request basic info
        cur.execute("""
            SELECT 
                sr.id,
                sr.title,
                sr.client_approval_stage,
                c.client_name
            FROM sales_request sr
            LEFT JOIN client c ON sr.client_id = c.id
            WHERE sr.id = %s
        """, (request_id,))
        
        request_info = cur.fetchone()
        
        if not request_info:
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Request not found'
            }), 404
        
        # Get all items with their approval status
        cur.execute("""
            SELECT 
                i.id,
                i.name as item_name,
                i.description,
                i.qty,
                i.cost_per_item,
                i.sell_per_item,
                i.approval_status,
                i.submitted_for_approval_date,
                i.client_approval_date,
                i.client_feedback,
                u.name as submitted_by_name
            FROM sales_request_items i
            LEFT JOIN user u ON i.submitted_by = u.id
            WHERE i.request_id = %s
            ORDER BY i.id ASC
        """, (request_id,))
        
        items = cur.fetchall()
        
        # Calculate statistics
        total_items = len(items)
        not_priced = sum(1 for item in items if not item['cost_per_item'] or not item['sell_per_item'])
        pending = sum(1 for item in items if (item['cost_per_item'] and item['sell_per_item']) and (not item['approval_status'] or item['approval_status'] == 'pending'))
        approved = sum(1 for item in items if item['approval_status'] == 'approved')
        rejected = sum(1 for item in items if item['approval_status'] == 'rejected')
        negotiation = sum(1 for item in items if item['approval_status'] == 'pending_negotiation')
        
        # Determine overall stage description
        stage = request_info['client_approval_stage']
        stage_descriptions = {
            'not_submitted': 'Items not yet submitted for client approval',
            'pending': 'Waiting for client approval',
            'partially_approved': 'Some items approved, others pending',
            'approved': 'All items approved by client',
            'rejected': 'Some items rejected by client'
        }
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'request': {
                'id': request_info['id'],
                'title': request_info['title'],
                'client_name': request_info['client_name'],
                'approval_stage': stage,
                'stage_description': stage_descriptions.get(stage, 'Unknown stage')
            },
            'statistics': {
                'total_items': total_items,
                'not_priced': not_priced,
                'pending': pending,
                'approved': approved,
                'rejected': rejected,
                'negotiation': negotiation
            },
            'items': items
        })
        
    except Exception as e:
        print(f"Error fetching approval stage: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Helper function to update request approval stage after item status changes
def update_request_approval_stage(request_id, conn=None, cur=None):
    """
    Update the client_approval_stage of a request based on its items' approval status
    Should be called after any item approval status changes
    """
    own_connection = False
    try:
        if not conn or not cur:
            conn, cur = connection()
            own_connection = True
        
        cur.execute("""
            UPDATE sales_request sr
            SET client_approval_stage = (
                SELECT CASE
                    -- All items approved
                    WHEN COUNT(CASE WHEN sri.approval_status = 'approved' THEN 1 END) = COUNT(*) 
                         AND COUNT(*) > 0
                    THEN 'approved'
                    
                    -- All items rejected
                    WHEN COUNT(CASE WHEN sri.approval_status = 'rejected' THEN 1 END) = COUNT(*)
                         AND COUNT(*) > 0
                    THEN 'rejected'
                    
                    -- Some items approved or rejected (partial)
                    WHEN COUNT(CASE WHEN sri.approval_status IN ('approved', 'rejected') THEN 1 END) > 0
                         AND COUNT(CASE WHEN sri.approval_status = 'approved' THEN 1 END) < COUNT(*)
                    THEN 'partially_approved'
                    
                    -- All items pending review (have prices, waiting for client)
                    WHEN COUNT(CASE WHEN sri.approval_status = 'pending' THEN 1 END) = COUNT(*)
                         AND COUNT(*) > 0
                         AND COUNT(CASE WHEN sri.cost_per_item IS NOT NULL AND sri.sell_per_item IS NOT NULL THEN 1 END) = COUNT(*)
                    THEN 'pending'
                    
                    -- Items not costed yet
                    WHEN COUNT(CASE WHEN sri.cost_per_item IS NULL THEN 1 END) > 0
                    THEN 'not_costed'
                    
                    -- Default: not submitted
                    ELSE 'not_submitted'
                END
                FROM sales_request_items sri
                WHERE sri.request_id = sr.id
            )
            WHERE sr.id = %s
        """, (request_id,))
        
        if own_connection:
            conn.commit()
            cur.close()
            conn.close()
        
        return True
        
    except Exception as e:
        print(f"Error updating request approval stage: {str(e)}")
        if own_connection and conn:
            try:
                cur.close()
                conn.close()
            except:
                pass
        return False

# ============================================================================
# END CLIENT APPROVAL API ENDPOINTS
# ============================================================================

# ============================================================================
# SALES REQUEST COMMENTS & NOTES SYSTEM WITH @MENTIONS
# ============================================================================

@app.route('/api/sales/requests/<int:request_id>/comments', methods=['GET'])
@perm('sales_request.comment')
def get_sales_request_comments(request_id):
    """Get all comments for a sales request with mentions"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Get filter parameters
        source_filter = request.args.get('source', '')
        show_notes = request.args.get('show_notes', 'true').lower() == 'true'
        
        # Build query
        query = """
            SELECT 
                c.id,
                c.request_id,
                c.comment_text,
                c.source,
                c.is_note,
                c.parent_comment_id,
                c.created_at,
                c.updated_at,
                c.user_id,
                u.name as user_name,
                u.mobile as user_mobile,
                (SELECT COUNT(*) FROM sales_request_comment_mentions WHERE comment_id = c.id) as mention_count,
                (SELECT GROUP_CONCAT(mu.name SEPARATOR ', ') 
                 FROM sales_request_comment_mentions m 
                 JOIN user mu ON m.mentioned_user_id = mu.id 
                 WHERE m.comment_id = c.id) as mentioned_users
            FROM sales_request_comments c
            JOIN user u ON c.user_id = u.id
            WHERE c.request_id = %s AND c.is_deleted = FALSE
        """
        
        params = [request_id]
        
        if source_filter:
            query += " AND c.source = %s"
            params.append(source_filter)
        
        if not show_notes:
            query += " AND c.is_note = FALSE"
        
        query += " ORDER BY c.created_at DESC"
        
        cur.execute(query, params)
        comments = cur.fetchall()
        
        # Get my mentions count
        cur.execute("""
            SELECT COUNT(*) as unread_mentions
            FROM sales_request_comment_mentions m
            JOIN sales_request_comments c ON m.comment_id = c.id
            WHERE m.mentioned_user_id = %s 
            AND m.is_read = FALSE
            AND c.request_id = %s
            AND c.is_deleted = FALSE
        """, (session['user_id'], request_id))
        
        unread_mentions = cur.fetchone()['unread_mentions']
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'comments': comments,
            'unread_mentions': unread_mentions
        })
        
    except Exception as e:
        print(f"Error fetching comments: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sales/requests/<int:request_id>/comments', methods=['POST'])
@perm('sales_request.comment')
def add_sales_request_comment(request_id):
    """Add a comment/note to a sales request with @mention support"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        comment_text = data.get('comment_text', '').strip()
        source = data.get('source', 'general')
        is_note = data.get('is_note', False)
        parent_comment_id = data.get('parent_comment_id')
        mentioned_user_ids = data.get('mentioned_users', [])  # List of user IDs
        
        if not comment_text:
            return jsonify({'success': False, 'error': 'Comment text is required'}), 400
        
        # Validate source
        valid_sources = ['general', 'client_approval', 'costing', 'selling_price', 
                        'operations', 'logistics', 'design', 'production']
        if source not in valid_sources:
            source = 'general'
        
        conn, cur = connection()
        user_id = session['user_id']
        user_name = session.get('name', 'Unknown User')
        
        # Verify request exists
        cur.execute("SELECT id, title FROM sales_request WHERE id = %s", (request_id,))
        request_info = cur.fetchone()
        
        if not request_info:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Request not found'}), 404
        
        # Insert comment
        cur.execute("""
            INSERT INTO sales_request_comments 
            (request_id, user_id, comment_text, source, is_note, parent_comment_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (request_id, user_id, comment_text, source, is_note, parent_comment_id))
        
        comment_id = cur.lastrowid
        
        # Process mentions
        notification_sent_to = []
        if mentioned_user_ids:
            for mentioned_user_id in mentioned_user_ids:
                try:
                    # Insert mention
                    cur.execute("""
                        INSERT INTO sales_request_comment_mentions 
                        (comment_id, mentioned_user_id)
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE comment_id = comment_id
                    """, (comment_id, mentioned_user_id))
                    
                    # Get mentioned user info
                    cur.execute("""
                        SELECT name, mobile FROM user WHERE id = %s
                    """, (mentioned_user_id,))
                    
                    mentioned_user = cur.fetchone()
                    
                    if mentioned_user:
                        # Send notification
                        notification_title = f"{user_name} mentioned you in a comment"
                        notification_body = f"Request #{request_id}: {comment_text[:100]}{'...' if len(comment_text) > 100 else ''}"
                        
                        # Add to notifications table
                        cur.execute("""
                            INSERT INTO notifications 
                            (user_id, title, content, notification_type, reference_id, reference_type)
                            VALUES (%s, %s, %s, 'mention', %s, 'sales_request')
                        """, (mentioned_user_id, notification_title, notification_body, request_id))
                        
                        # Try to send push notification
                        try:
                            if mentioned_user['mobile']:
                                push_send_notification(
                                    mentioned_user['mobile'],
                                    notification_title,
                                    notification_body
                                )
                                notification_sent_to.append(mentioned_user['name'])
                        except Exception as push_error:
                            print(f"Push notification error: {str(push_error)}")
                    
                except Exception as mention_error:
                    print(f"Error processing mention for user {mentioned_user_id}: {str(mention_error)}")
        
        # Log the comment in change log
        source_labels = {
            'general': 'General',
            'client_approval': 'Client Approval',
            'costing': 'Costing',
            'selling_price': 'Selling Price',
            'operations': 'Operations',
            'logistics': 'Logistics',
            'design': 'Design',
            'production': 'Production'
        }
        
        comment_type = "Note" if is_note else "Comment"
        description = f"{comment_type} added in {source_labels.get(source, source)}: {comment_text[:100]}{'...' if len(comment_text) > 100 else ''}"
        
        log_request_change(
            request_id=request_id,
            action_type='comment_added',
            action_by=user_name,
            change_description=description,
            conn=conn,
            cur=cur
        )
        
        conn.commit()
        
        # Get the created comment with user info
        cur.execute("""
            SELECT 
                c.id,
                c.comment_text,
                c.source,
                c.is_note,
                c.created_at,
                u.name as user_name
            FROM sales_request_comments c
            JOIN user u ON c.user_id = u.id
            WHERE c.id = %s
        """, (comment_id,))
        
        created_comment = cur.fetchone()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'{comment_type} added successfully',
            'comment': created_comment,
            'notifications_sent': len(notification_sent_to),
            'notified_users': notification_sent_to
        })
        
    except Exception as e:
        print(f"Error adding comment: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sales/requests/comments/<int:comment_id>', methods=['PUT'])
@perm('sales_request.comment')
def update_sales_request_comment(comment_id):
    """Update a comment (only by the author)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        comment_text = data.get('comment_text', '').strip()
        
        if not comment_text:
            return jsonify({'success': False, 'error': 'Comment text is required'}), 400
        
        conn, cur = connection()
        user_id = session['user_id']
        
        # Verify ownership
        cur.execute("""
            SELECT user_id, request_id FROM sales_request_comments 
            WHERE id = %s AND is_deleted = FALSE
        """, (comment_id,))
        
        comment = cur.fetchone()
        
        if not comment:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Comment not found'}), 404
        
        if comment['user_id'] != user_id:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Update comment
        cur.execute("""
            UPDATE sales_request_comments 
            SET comment_text = %s, updated_at = NOW()
            WHERE id = %s
        """, (comment_text, comment_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Comment updated successfully'
        })
        
    except Exception as e:
        print(f"Error updating comment: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sales/requests/comments/<int:comment_id>', methods=['DELETE'])
@perm('sales_request.comment')
def delete_sales_request_comment(comment_id):
    """Soft delete a comment (only by author or admin)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        user_id = session['user_id']
        user_roles = session.get('roles', [])
        
        # Get comment info
        cur.execute("""
            SELECT user_id, request_id FROM sales_request_comments 
            WHERE id = %s AND is_deleted = FALSE
        """, (comment_id,))
        
        comment = cur.fetchone()
        
        if not comment:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Comment not found'}), 404
        
        # Check permission (author or admin)
        if comment['user_id'] != user_id and 'admin' not in user_roles:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Soft delete
        cur.execute("""
            UPDATE sales_request_comments 
            SET is_deleted = TRUE, deleted_at = NOW(), deleted_by = %s
            WHERE id = %s
        """, (user_id, comment_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Comment deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting comment: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sales/requests/comments/<int:comment_id>/mentions/read', methods=['POST'])
@perm('sales_request.comment')
def mark_mention_as_read(comment_id):
    """Mark a mention as read"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        user_id = session['user_id']
        
        cur.execute("""
            UPDATE sales_request_comment_mentions 
            SET is_read = TRUE, read_at = NOW()
            WHERE comment_id = %s AND mentioned_user_id = %s
        """, (comment_id, user_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Mention marked as read'
        })
        
    except Exception as e:
        print(f"Error marking mention as read: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/chat/sr-list', methods=['GET'])
@perm('sales_request.view')
def get_chat_sr_list():
    """
    Global chat list for the slide-in chat drawer.
    Returns every sales request that has at least one comment, along with the
    latest message preview, total message count, and how many mentions of the
    current user are still unread in that request.
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    try:
        conn, cur = connection()
        user_id = session['user_id']

        scope_sql, scope_params = scope_clause('sales_request.view', 'sr.owner_user_id')

        cur.execute(
            """
            SELECT
                sr.id            AS request_id,
                sr.title         AS title,
                cl.client_name   AS client_name,
                comp.company_name AS company_name,
                COALESCE(stats.total_messages, 0) AS total_messages,
                stats.last_message_at,
                lm.comment_text  AS last_message_text,
                lm.user_id       AS last_message_user_id,
                lu.name          AS last_message_user_name,
                COALESCE(unread.unread_mentions, 0) AS unread_mentions,
                sr.created_at    AS sr_created_at
            FROM sales_request sr
            LEFT JOIN (
                SELECT request_id,
                       COUNT(*)        AS total_messages,
                       MAX(created_at) AS last_message_at,
                       MAX(id)         AS last_comment_id
                FROM sales_request_comments
                WHERE is_deleted = 0
                GROUP BY request_id
            ) stats ON stats.request_id = sr.id
            LEFT JOIN sales_request_comments lm ON lm.id = stats.last_comment_id
            LEFT JOIN user lu ON lu.id = lm.user_id
            LEFT JOIN client cl ON cl.id = sr.client_id
            LEFT JOIN company comp ON comp.id = sr.company_id
            LEFT JOIN (
                SELECT c.request_id,
                       COUNT(*) AS unread_mentions
                FROM sales_request_comment_mentions m
                JOIN sales_request_comments c ON c.id = m.comment_id
                WHERE m.mentioned_user_id = %s
                  AND m.is_read = 0
                  AND c.is_deleted = 0
                GROUP BY c.request_id
            ) unread ON unread.request_id = sr.id
            WHERE 1=1 """ + scope_sql + """
            ORDER BY COALESCE(stats.last_message_at, sr.created_at) DESC
            LIMIT 500
            """,
            [user_id] + scope_params
        )
        rows = cur.fetchall() or []

        chats = []
        total_unread = 0
        for r in rows:
            unread = int(r.get('unread_mentions') or 0)
            total_unread += unread
            preview = (r.get('last_message_text') or '')
            if len(preview) > 120:
                preview = preview[:117] + '...'
            last_at = r.get('last_message_at')
            chats.append({
                'request_id': r.get('request_id'),
                'title': r.get('title') or '',
                'client_name': r.get('client_name') or '',
                'company_name': r.get('company_name') or '',
                'total_messages': int(r.get('total_messages') or 0),
                'last_message_text': preview,
                'last_message_user': r.get('last_message_user_name') or '',
                'last_message_at': last_at.strftime('%Y-%m-%d %H:%M:%S') if last_at else None,
                'sr_created_at': r['sr_created_at'].strftime('%Y-%m-%d %H:%M:%S') if r.get('sr_created_at') else None,
                'unread_mentions': unread,
            })

        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'chats': chats,
            'total_unread': total_unread,
        })

    except Exception as e:
        print(f"Error fetching chat SR list: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/chat/sr/<int:request_id>/mark-read', methods=['POST'])
@perm('sales_request.comment')
def mark_chat_sr_read(request_id):
    """Mark every mention of the current user as read for the given sales request.
    Called by the chat drawer when the user opens a chat thread.
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    try:
        conn, cur = connection()
        user_id = session['user_id']
        cur.execute(
            """
            UPDATE sales_request_comment_mentions m
            JOIN sales_request_comments c ON c.id = m.comment_id
            SET m.is_read = 1, m.read_at = NOW()
            WHERE m.mentioned_user_id = %s
              AND m.is_read = 0
              AND c.request_id = %s
              AND c.is_deleted = 0
            """,
            (user_id, request_id)
        )
        affected = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True, 'marked_read': affected})
    except Exception as e:
        print(f"Error marking chat SR as read: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sales/my-mentions', methods=['GET'])
@perm('sales_request.comment')
def get_my_mentions():
    """Get all mentions for the current user across all requests"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        user_id = session['user_id']
        
        # Get only unread or get all based on query param
        only_unread = request.args.get('only_unread', 'false').lower() == 'true'
        
        query = """
            SELECT 
                c.id as comment_id,
                c.request_id,
                c.comment_text,
                c.source,
                c.created_at,
                u.name as author_name,
                sr.title as request_title,
                m.is_read,
                m.read_at
            FROM sales_request_comment_mentions m
            JOIN sales_request_comments c ON m.comment_id = c.id
            JOIN user u ON c.user_id = u.id
            JOIN sales_request sr ON c.request_id = sr.id
            WHERE m.mentioned_user_id = %s AND c.is_deleted = FALSE
        """
        
        if only_unread:
            query += " AND m.is_read = FALSE"
        
        query += " ORDER BY c.created_at DESC LIMIT 50"
        
        cur.execute(query, (user_id,))
        mentions = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'mentions': mentions
        })
        
    except Exception as e:
        print(f"Error fetching mentions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/users/search', methods=['GET'])
@perm('sales_request.comment')
def search_users_for_mention():
    """Search users for @mention functionality"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        search_term = request.args.get('q', '').strip()
        
        # Allow empty search to show all users when @ is typed
        # if len(search_term) < 2:
        #     return jsonify({'success': True, 'users': []})
        
        conn, cur = connection()
        
        # If no search term, return all active users
        if not search_term:
            cur.execute("""
                SELECT 
                    id,
                    name,
                    mobile
                FROM user
                WHERE id != %s
                ORDER BY name
                LIMIT 50
            """, (session['user_id'],))
        else:
            # Search by name or mobile
            cur.execute("""
                SELECT 
                    id,
                    name,
                    mobile
                FROM user
                WHERE (name LIKE %s OR mobile LIKE %s)
                AND id != %s
                ORDER BY name
                LIMIT 20
            """, (f'%{search_term}%', f'%{search_term}%', session['user_id']))
        
        users = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'users': users
        })
        
    except Exception as e:
        print(f"Error searching users: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# END SALES REQUEST COMMENTS & NOTES SYSTEM
# ============================================================================

# ============================================================================
# ENTITY MANAGEMENT SYSTEM
# ============================================================================

@app.route('/entity-management', methods=['GET'])
@perm('entity.view')
def entity_management_page():
    """Render the Entity Management page"""
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('entity_management.html')

@app.route('/inventory-selection', methods=['GET'])
@perm('inventory.view')
def inventory_selection_page():
    """Render the Inventory Selection Landing page"""
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('inventory_selection.html')

@app.route('/api/entities', methods=['GET'])
@perm('entity.view')
def get_entities():
    """Get all entities with statistics"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Get all entities with inventory item counts
        cur.execute("""
            SELECT 
                e.*,
                COUNT(DISTINCT i.id) as items_count,
                COALESCE(SUM(i.quantity_in_stock), 0) as total_stock,
                COALESCE(SUM(i.quantity_in_stock * i.average_cost), 0) as inventory_value
            FROM entities e
            LEFT JOIN inventory_items i ON e.id = i.entity_id AND i.is_credit_item = FALSE
            GROUP BY e.id
            ORDER BY e.created_at DESC
        """)
        entities = cur.fetchall()
        
        # Get statistics
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN status = 'inactive' THEN 1 ELSE 0 END) as inactive
            FROM entities
        """)
        stats_row = cur.fetchone()
        
        # Get total inventory items across all entities
        cur.execute("SELECT COUNT(*) as total_items FROM inventory_items WHERE is_credit_item = FALSE")
        items_row = cur.fetchone()
        
        stats = {
            'total': stats_row['total'] if stats_row else 0,
            'active': stats_row['active'] if stats_row else 0,
            'inactive': stats_row['inactive'] if stats_row else 0,
            'total_items': items_row['total_items'] if items_row else 0
        }
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'entities': entities,
            'stats': stats
        })
        
    except Exception as e:
        print(f"Error getting entities: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/entities', methods=['POST'])
@perm('entity.create')
def create_entity():
    """Create a new entity"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        
        entity_name = data.get('entity_name', '').strip()
        entity_code = data.get('entity_code', '').strip().upper()
        
        if not entity_name or not entity_code:
            return jsonify({'success': False, 'error': 'Entity name and code are required'}), 400
        
        conn, cur = connection()
        
        # Check for duplicate name or code
        cur.execute("SELECT id FROM entities WHERE entity_name = %s OR entity_code = %s", (entity_name, entity_code))
        existing = cur.fetchone()
        if existing:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'An entity with this name or code already exists'}), 400
        
        # Insert new entity
        cur.execute("""
            INSERT INTO entities (entity_name, entity_code, description, address, contact_person, 
                                  contact_phone, contact_email, logo_url, status, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            entity_name,
            entity_code,
            data.get('description', ''),
            data.get('address', ''),
            data.get('contact_person', ''),
            data.get('contact_phone', ''),
            data.get('contact_email', ''),
            data.get('logo_url', ''),
            data.get('status', 'active'),
            session.get('username', 'system')
        ))
        
        entity_id = cur.lastrowid
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Entity created successfully',
            'entity_id': entity_id
        })
        
    except Exception as e:
        print(f"Error creating entity: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/entities/<int:entity_id>', methods=['GET'])
@perm('entity.view')
def get_entity(entity_id):
    """Get single entity details"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        cur.execute("SELECT * FROM entities WHERE id = %s", (entity_id,))
        entity = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if not entity:
            return jsonify({'success': False, 'error': 'Entity not found'}), 404
        
        return jsonify({
            'success': True,
            'entity': entity
        })
        
    except Exception as e:
        print(f"Error getting entity: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/entities/<int:entity_id>', methods=['PUT'])
@perm('entity.edit')
def update_entity(entity_id):
    """Update an entity"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        
        conn, cur = connection()
        
        # Check entity exists
        cur.execute("SELECT id FROM entities WHERE id = %s", (entity_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Entity not found'}), 404
        
        # Check for duplicate name or code (excluding current entity)
        entity_name = data.get('entity_name', '').strip()
        entity_code = data.get('entity_code', '').strip().upper()
        
        cur.execute("""
            SELECT id FROM entities 
            WHERE (entity_name = %s OR entity_code = %s) AND id != %s
        """, (entity_name, entity_code, entity_id))
        
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'An entity with this name or code already exists'}), 400
        
        # Update entity
        cur.execute("""
            UPDATE entities SET 
                entity_name = %s,
                entity_code = %s,
                description = %s,
                address = %s,
                contact_person = %s,
                contact_phone = %s,
                contact_email = %s,
                logo_url = %s,
                status = %s
            WHERE id = %s
        """, (
            entity_name,
            entity_code,
            data.get('description', ''),
            data.get('address', ''),
            data.get('contact_person', ''),
            data.get('contact_phone', ''),
            data.get('contact_email', ''),
            data.get('logo_url', ''),
            data.get('status', 'active'),
            entity_id
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Entity updated successfully'
        })
        
    except Exception as e:
        print(f"Error updating entity: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/entities/<int:entity_id>', methods=['DELETE'])
@perm('entity.delete')
def delete_entity(entity_id):
    """Delete an entity (only if no inventory items)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Check for existing inventory items
        cur.execute("SELECT COUNT(*) as count FROM inventory_items WHERE entity_id = %s", (entity_id,))
        count = cur.fetchone()['count']
        
        if count > 0:
            cur.close()
            conn.close()
            return jsonify({
                'success': False, 
                'error': f'Cannot delete entity with {count} inventory items. Remove or reassign items first.'
            }), 400
        
        # Delete entity
        cur.execute("DELETE FROM entities WHERE id = %s", (entity_id,))
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Entity deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting entity: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/entities/inventory-stats', methods=['GET'])
@perm('inventory.view')
def get_entities_inventory_stats():
    """Get all entities with inventory statistics for landing page"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Get entities with detailed stats
        cur.execute("""
            SELECT 
                e.id, e.entity_name, e.entity_code, e.logo_url, e.status, e.description,
                COUNT(DISTINCT i.id) as total_items,
                COALESCE(SUM(i.quantity_in_stock), 0) as total_stock,
                COALESCE(SUM(i.quantity_in_stock * i.average_cost), 0) as total_inventory_value,
                SUM(CASE WHEN i.quantity_in_stock <= i.minimum_stock_level AND i.quantity_in_stock > 0 THEN 1 ELSE 0 END) as low_stock_items,
                SUM(CASE WHEN i.quantity_in_stock = 0 THEN 1 ELSE 0 END) as out_of_stock_items
            FROM entities e
            LEFT JOIN inventory_items i ON e.id = i.entity_id AND i.is_credit_item = FALSE AND i.status = 'active'
            WHERE e.status = 'active'
            GROUP BY e.id, e.entity_name, e.entity_code, e.logo_url, e.status, e.description
            ORDER BY e.entity_name ASC
        """)
        entities = cur.fetchall()
        
        # Get global stats
        cur.execute("""
            SELECT 
                (SELECT COUNT(*) FROM entities WHERE status = 'active') as total_entities,
                COUNT(DISTINCT i.id) as total_items,
                COALESCE(SUM(i.quantity_in_stock), 0) as total_stock,
                (SELECT COUNT(*) FROM inventory_items WHERE is_credit_item = TRUE AND status = 'active') as credit_items
            FROM inventory_items i
            WHERE i.is_credit_item = FALSE AND i.status = 'active'
        """)
        global_stats = cur.fetchone()
        
        # Get credit inventory stats
        cur.execute("""
            SELECT 
                COUNT(DISTINCT i.id) as total_items,
                COALESCE(SUM(i.quantity_in_stock), 0) as total_stock,
                COUNT(DISTINCT c.supplier_id) as supplier_count,
                COALESCE(SUM(c.amount_due), 0) as total_amount_due
            FROM inventory_items i
            LEFT JOIN inventory_credit_items c ON i.id = c.item_id
            WHERE i.is_credit_item = TRUE AND i.status = 'active'
        """)
        credit_stats = cur.fetchone()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'entities': entities,
            'global_stats': global_stats,
            'credit_stats': credit_stats
        })
        
    except Exception as e:
        print(f"Error getting entity inventory stats: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# ITEM MANAGEMENT & INVENTORY SYSTEM
# ============================================================================

@app.route('/item_management', methods=['GET'])
@perm('inventory.view')
def item_management_page():
    """Redirect to new inventory management page"""
    if 'user_id' not in session:
        return redirect('/login')
    
    # Redirect to inventory selection landing page
    return redirect('/inventory-selection')

# ============================================================================
# FINANCE PAGE ROUTE
# ============================================================================

@app.route('/finance_management', methods=['GET'])
@perm('finance_txn.view')
def finance_management_page():
    """Render the Finance Management page (detailed tabs)"""
    if 'user_id' not in session:
        return redirect('/login')
    
    return render_template('finance_management.html')

@app.route('/finance', methods=['GET'])
@perm('finance_txn.view')
def finance_section_page():
    """Display finance section landing page with dashboard and sub-page links"""
    if 'user_id' not in session:
        return redirect('/login')
    
    return render_template('finance_section.html')

# ============================================================================
# INVENTORY PAGE ROUTE
# ============================================================================

@app.route('/inventory_management', methods=['GET'])
@app.route('/inventory', methods=['GET'])
@perm('inventory.view')
def inventory_management_page():
    """Render the NEW modern inventory management page with separated regular/credit"""
    if 'user_id' not in session:
        return redirect('/login')
    
    # Get entity_id or type from URL params
    entity_id = request.args.get('entity_id')
    inventory_type = request.args.get('type')  # 'credit' for credit inventory
    
    # If no entity_id and not credit type, redirect to selection page
    if not entity_id and inventory_type != 'credit':
        return redirect('/inventory-selection')
    
    # Get entity info if entity_id provided
    entity_info = None
    if entity_id:
        try:
            conn, cur = connection()
            cur.execute("SELECT id, entity_name, entity_code FROM entities WHERE id = %s", (entity_id,))
            entity_info = cur.fetchone()
            cur.close()
            conn.close()
        except:
            pass
    
    return render_template('inventory_management.html', 
                         entity_id=entity_id, 
                         entity_info=entity_info,
                         inventory_type=inventory_type)

@app.route('/api/inventory/items', methods=['GET'])
@perm('inventory.view')
def get_inventory_items():
    """Get all inventory items with stock levels and component details"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Get inventory type filter from query params (regular, credit, or all)
        inventory_type = request.args.get('type', 'all')
        entity_id = request.args.get('entity_id')
        
        # Build query based on inventory type and entity
        where_conditions = []
        params = []
        
        if inventory_type == 'regular':
            where_conditions.append("i.is_credit_item = FALSE")
        elif inventory_type == 'credit':
            where_conditions.append("i.is_credit_item = TRUE")
        
        # Filter by entity for regular inventory
        if entity_id and inventory_type != 'credit':
            where_conditions.append("i.entity_id = %s")
            params.append(entity_id)
        
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # Get all items with supplier info and dimensions/specifications
        query = f"""
            SELECT 
                i.id, i.item_code, i.item_name, i.item_type, i.category,
                i.description, i.unit_of_measure, i.quantity_in_stock,
                i.minimum_stock_level, i.reorder_level, i.average_cost,
                i.last_purchase_cost, i.preferred_supplier_id, i.source_type,
                i.source_id, i.status, i.created_by, i.created_at, i.updated_at,
                i.width, i.height, i.depth, i.specifications, i.request_type,
                i.is_credit_item, i.credit_supplier_id, i.entity_id,
                s.supplier_name,
                cs.supplier_name as credit_supplier_name,
                e.entity_name, e.entity_code
            FROM inventory_items i
            LEFT JOIN supplier s ON i.preferred_supplier_id = s.id
            LEFT JOIN supplier cs ON i.credit_supplier_id = cs.id
            LEFT JOIN entities e ON i.entity_id = e.id
            {where_clause}
            ORDER BY i.id DESC
        """
        cur.execute(query, params)
        items = cur.fetchall()
        
        items_list = []
        for item in items:
            # For credit items, get credit details
            credit_details = None
            if item['is_credit_item']:
                cur.execute("""
                    SELECT 
                        c.id as credit_id, c.quantity_received, c.quantity_sold, c.quantity_returned,
                        c.quantity_remaining, c.agreed_cost_per_item, c.payment_status,
                        c.amount_due, c.amount_paid, c.received_date, c.due_date, c.status as credit_status,
                        s.supplier_name, c.sales_request_item_id
                    FROM inventory_credit_items c
                    LEFT JOIN supplier s ON c.supplier_id = s.id
                    WHERE c.item_id = %s AND c.status = 'active'
                    LIMIT 1
                """, (item['id'],))
                credit_data = cur.fetchone()
                if credit_data:
                    credit_details = dict(credit_data)
            
            # Get components if composite item
            components = []
            if item['item_type'] == 'composite':
                cur.execute("""
                    SELECT 
                        ic.id, ic.quantity_required, ic.unit_of_measure, ic.notes,
                        i.id as component_id, i.item_code, i.item_name, i.quantity_in_stock
                    FROM inventory_item_components ic
                    JOIN inventory_items i ON ic.component_item_id = i.id
                    WHERE ic.parent_item_id = %s
                """, (item['id'],))
                components = [dict(comp) for comp in cur.fetchall()]
            
            # Check for alerts
            cur.execute("""
                SELECT COUNT(*) as alert_count
                FROM inventory_alerts
                WHERE item_id = %s AND is_resolved = FALSE
            """, (item['id'],))
            alert_count = cur.fetchone()['alert_count']
            
            item_data = {
                'id': item['id'],
                'item_code': item['item_code'],
                'item_name': item['item_name'],
                'item_type': item['item_type'],
                'category': item['category'],
                'description': item['description'],
                'unit_of_measure': item['unit_of_measure'],
                'quantity_in_stock': float(item['quantity_in_stock']) if item['quantity_in_stock'] else 0,
                'minimum_stock_level': item['minimum_stock_level'],
                'reorder_level': item['reorder_level'],
                'average_cost': float(item['average_cost']) if item['average_cost'] else 0,
                'last_purchase_cost': float(item['last_purchase_cost']) if item['last_purchase_cost'] else 0,
                'preferred_supplier_id': item['preferred_supplier_id'],
                'supplier_name': item['supplier_name'],
                'source_type': item['source_type'],
                'status': item['status'],
                'created_by': item['created_by'],
                'created_at': item['created_at'].strftime('%Y-%m-%d %H:%M:%S') if item['created_at'] else '',
                # Include dimensions and specifications
                'width': float(item['width']) if item['width'] else None,
                'height': float(item['height']) if item['height'] else None,
                'depth': float(item['depth']) if item['depth'] else None,
                'specifications': item['specifications'],
                'request_type': item['request_type'],
                # Include inventory type flag
                'is_credit_item': item['is_credit_item'],
                'credit_supplier_id': item['credit_supplier_id'],
                'credit_supplier_name': item.get('credit_supplier_name'),
                # Include entity information
                'entity_id': item.get('entity_id'),
                'entity_name': item.get('entity_name'),
                'entity_code': item.get('entity_code'),
                # Include related data
                'components': components,
                'credit_details': credit_details,
                'alert_count': alert_count
            }
            items_list.append(item_data)
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'items': items_list})
        
    except Exception as e:
        print(f"Error getting inventory items: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/items/add', methods=['POST'])
@perm('inventory.create')
def add_inventory_item():
    """Add a new inventory item (simple or composite)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        conn, cur = connection()
        
        # Extract new sales-related fields with proper null handling
        sales_request_item_id = data.get('sales_request_item_id') or None
        unit_selling_price = float(data.get('unit_selling_price', 0))
        average_cost = float(data.get('average_cost', 0))
        is_credit_item = data.get('is_credit_item', False)
        credit_supplier_id = data.get('credit_supplier_id') or None
        preferred_supplier_id = data.get('preferred_supplier_id') or None
        entity_id = data.get('entity_id') or None  # NEW: Entity isolation
        
        # NEW: Extract dimensions and specifications from sales request item
        width = float(data.get('width')) if data.get('width') else None
        height = float(data.get('height')) if data.get('height') else None
        depth = float(data.get('depth')) if data.get('depth') else None
        specifications = data.get('specifications')
        request_type = data.get('request_type')
        
        # Calculate expected profit
        expected_profit_per_unit = unit_selling_price - average_cost if unit_selling_price and average_cost else 0
        
        # Generate unique item_code if provided code already exists or is same as item_name
        item_code = data.get('item_code')
        item_name = data.get('item_name')
        
        # Check if item_code is same as item_name or already exists
        if item_code == item_name or not item_code:
            # Generate new code
            cur.execute("SELECT MAX(CAST(SUBSTRING(item_code, 5) AS UNSIGNED)) as max_num FROM inventory_items WHERE item_code LIKE 'INV-%'")
            result = cur.fetchone()
            next_num = (result['max_num'] or 0) + 1
            item_code = f'INV-{next_num:05d}'
        else:
            # Check if provided code already exists
            cur.execute("SELECT id FROM inventory_items WHERE item_code = %s", (item_code,))
            if cur.fetchone():
                # Code exists, generate new one
                cur.execute("SELECT MAX(CAST(SUBSTRING(item_code, 5) AS UNSIGNED)) as max_num FROM inventory_items WHERE item_code LIKE 'INV-%'")
                result = cur.fetchone()
                next_num = (result['max_num'] or 0) + 1
                item_code = f'INV-{next_num:05d}'
        
        # Check if item already exists based on unique constraint (name, unit, dimensions)
        unit_of_measure = data.get('unit_of_measure', 'PCS')
        check_query = """
            SELECT id, item_code, item_name FROM inventory_items 
            WHERE item_name = %s 
            AND unit_of_measure = %s
        """
        check_params = [item_name, unit_of_measure]
        
        # Add dimension checks (handle NULL values)
        if width is not None:
            check_query += " AND width = %s"
            check_params.append(width)
        else:
            check_query += " AND width IS NULL"
            
        if height is not None:
            check_query += " AND height = %s"
            check_params.append(height)
        else:
            check_query += " AND height IS NULL"
            
        if depth is not None:
            check_query += " AND depth = %s"
            check_params.append(depth)
        else:
            check_query += " AND depth IS NULL"
        
        cur.execute(check_query, check_params)
        existing_item = cur.fetchone()
        
        if existing_item:
            # Item already exists - return existing item info
            cur.close()
            conn.close()
            return jsonify({
                'success': True, 
                'item_id': existing_item['id'],
                'item_code': existing_item['item_code'],
                'message': 'Item already exists',
                'already_exists': True
            })
        
        # Get initial quantity before insertion (will be added via transaction)
        initial_quantity = int(data.get('quantity_in_stock', 0))
        
        # Insert main item with dimensions and specifications - START WITH 0 STOCK
        # Stock will be added via transaction which triggers stock update
        cur.execute("""
            INSERT INTO inventory_items 
            (item_code, item_name, item_type, category, description, unit_of_measure,
             quantity_in_stock, minimum_stock_level, reorder_level, average_cost,
             preferred_supplier_id, source_type, status, created_by,
             sales_request_item_id, unit_selling_price, expected_profit_per_unit,
             is_credit_item, credit_supplier_id,
             width, height, depth, specifications, request_type, entity_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            item_code,  # Use generated/validated item_code
            data.get('item_name'),
            data.get('item_type', 'simple'),
            data.get('category'),
            data.get('description'),
            data.get('unit_of_measure', 'PCS'),
            0,  # Start with 0 stock - will be added via transaction
            data.get('minimum_stock_level', 0),
            data.get('reorder_level', 10),
            average_cost,
            preferred_supplier_id,
            data.get('source_type', 'manual'),
            data.get('status', 'active'),
            session.get('username'),
            sales_request_item_id,
            unit_selling_price,
            expected_profit_per_unit,
            is_credit_item,
            credit_supplier_id,
            width,
            height,
            depth,
            specifications,
            request_type,
            entity_id
        ))
        
        item_id = cur.lastrowid
        
        # Create initial transaction if quantity > 0 - trigger will update stock and set balance_after
        if initial_quantity > 0:
            cur.execute("""
                INSERT INTO inventory_transactions
                (item_id, entity_id, transaction_type, quantity, unit_cost, total_cost,
                 reference_type, notes, performed_by)
                VALUES (%s, %s, 'purchase', %s, %s, %s, 'initial_stock', %s, %s)
            """, (
                item_id,
                entity_id,
                initial_quantity,
                average_cost,
                initial_quantity * average_cost,
                f'Initial stock for {item_code}',
                session.get('username')
            ))
        
        # If composite item, add components
        if data.get('item_type') == 'composite' and data.get('components'):
            for component in data.get('components', []):
                cur.execute("""
                    INSERT INTO inventory_item_components
                    (parent_item_id, component_item_id, quantity_required, unit_of_measure, notes)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    item_id,
                    component.get('component_id'),
                    component.get('quantity_required', 1),
                    component.get('unit_of_measure', 'PCS'),
                    component.get('notes')
                ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'item_id': item_id, 'item_code': item_code, 'message': 'Item added successfully'})
        
    except Exception as e:
        print(f"Error adding inventory item: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/items/<int:item_id>', methods=['GET'])
@perm('inventory.view')
def get_inventory_item(item_id):
    """Get a single inventory item by ID"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        cur.execute("""
            SELECT 
                i.*,
                s.supplier_name AS supplier_name,
                cs.supplier_name AS credit_supplier_name
            FROM inventory_items i
            LEFT JOIN supplier s ON i.preferred_supplier_id = s.id
            LEFT JOIN supplier cs ON i.credit_supplier_id = cs.id
            WHERE i.id = %s
        """, (item_id,))
        
        item = cur.fetchone()
        cur.close()
        conn.close()
        
        if not item:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        
        return jsonify({
            'success': True,
            'item': dict(item)
        })
        
    except Exception as e:
        print(f"Error fetching inventory item: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/items/<int:item_id>', methods=['PUT'])
@perm('inventory.edit')
def update_inventory_item(item_id):
    """Update an inventory item"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        conn, cur = connection()
        
        # Build dynamic update query based on provided fields
        update_fields = []
        update_values = []
        
        field_mapping = {
            'item_name': 'item_name',
            'category': 'category',
            'description': 'description',
            'unit_of_measure': 'unit_of_measure',
            'minimum_stock_level': 'minimum_stock_level',
            'reorder_level': 'reorder_level',
            'preferred_supplier_id': 'preferred_supplier_id',
            'status': 'status',
            'width': 'width',
            'height': 'height',
            'depth': 'depth'
        }
        
        for form_field, db_field in field_mapping.items():
            if form_field in data and data[form_field] is not None:
                value = data[form_field]
                # Handle empty strings for numeric/foreign key fields
                if db_field in ['minimum_stock_level', 'reorder_level', 'width', 'height', 'depth']:
                    value = float(value) if value != '' else None
                elif db_field == 'preferred_supplier_id':
                    value = int(value) if value != '' else None
                update_fields.append(f"{db_field} = %s")
                update_values.append(value)
        
        if not update_fields:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'No fields to update'}), 400
        
        update_values.append(item_id)
        
        cur.execute(f"""
            UPDATE inventory_items
            SET {', '.join(update_fields)}
            WHERE id = %s
        """, tuple(update_values))
        
        # Update components if composite
        if data.get('item_type') == 'composite':
            # Delete existing components
            cur.execute("DELETE FROM inventory_item_components WHERE parent_item_id = %s", (item_id,))
            
            # Add new components
            for component in data.get('components', []):
                cur.execute("""
                    INSERT INTO inventory_item_components
                    (parent_item_id, component_item_id, quantity_required, unit_of_measure, notes)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    item_id,
                    component.get('component_id'),
                    component.get('quantity_required', 1),
                    component.get('unit_of_measure', 'PCS'),
                    component.get('notes')
                ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Item updated successfully'})
        
    except Exception as e:
        print(f"Error updating inventory item: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/items/<int:item_id>', methods=['DELETE'])
@perm('inventory.delete')
def delete_inventory_item(item_id):
    """Delete an inventory item"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Check if item has transactions
        cur.execute("SELECT COUNT(*) as count FROM inventory_transactions WHERE item_id = %s", (item_id,))
        has_transactions = cur.fetchone()['count'] > 0
        
        if has_transactions:
            # Soft delete - mark as inactive
            cur.execute("UPDATE inventory_items SET status = 'discontinued' WHERE id = %s", (item_id,))
        else:
            # Hard delete
            cur.execute("DELETE FROM inventory_items WHERE id = %s", (item_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Item deleted successfully'})
        
    except Exception as e:
        print(f"Error deleting inventory item: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/transactions', methods=['GET'])
@perm('inventory.view')
def get_inventory_transactions():
    """Get all inventory transactions with optional filters"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Get query parameters
        item_id = request.args.get('item_id')
        transaction_type = request.args.get('transaction_type')
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        days = request.args.get('days', type=int)
        inventory_type = request.args.get('inventory_type')  # 'regular' or 'credit'
        entity_id = request.args.get('entity_id')  # Filter by specific entity
        
        query = """
            SELECT 
                t.id, t.item_id, t.entity_id, t.transaction_type, t.quantity, t.unit_cost,
                t.total_cost, t.reference_type, t.reference_id, t.transaction_date,
                t.notes, t.performed_by, t.balance_after,
                i.item_code, i.item_name, i.is_credit_item, i.entity_id as item_entity_id,
                s.supplier_name,
                c.client_name,
                e.entity_name
            FROM inventory_transactions t
            LEFT JOIN inventory_items i ON t.item_id = i.id
            LEFT JOIN supplier s ON t.supplier_id = s.id
            LEFT JOIN client c ON t.client_id = c.id
            LEFT JOIN entities e ON COALESCE(t.entity_id, i.entity_id) = e.id
            WHERE 1=1
        """
        params = []
        
        if item_id:
            query += " AND t.item_id = %s"
            params.append(item_id)
        
        if transaction_type:
            query += " AND t.transaction_type = %s"
            params.append(transaction_type)
        
        # Filter by entity_id (for entity-based inventory)
        if entity_id:
            query += " AND (t.entity_id = %s OR i.entity_id = %s)"
            params.append(entity_id)
            params.append(entity_id)
        # Filter by inventory type (regular vs credit)
        elif inventory_type == 'regular':
            query += " AND (i.is_credit_item = FALSE OR i.is_credit_item IS NULL)"
        elif inventory_type == 'credit':
            query += " AND i.is_credit_item = TRUE"
        
        if from_date:
            query += " AND DATE(t.transaction_date) >= %s"
            params.append(from_date)
        
        if to_date:
            query += " AND DATE(t.transaction_date) <= %s"
            params.append(to_date)
        
        # If days specified and no explicit dates, filter by days
        if days and not from_date and not to_date:
            query += " AND t.transaction_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)"
            params.append(days)
        
        query += " ORDER BY t.transaction_date DESC LIMIT 500"
        
        cur.execute(query, params)
        transactions = cur.fetchall()
        
        transactions_list = []
        for trans in transactions:
            # Build reference info string
            ref_info = ''
            if trans['reference_type']:
                ref_info = f"{trans['reference_type']}"
                if trans['reference_id']:
                    ref_info += f" #{trans['reference_id']}"
            elif trans['supplier_name']:
                ref_info = f"Supplier: {trans['supplier_name']}"
            elif trans['client_name']:
                ref_info = f"Client: {trans['client_name']}"
            
            transactions_list.append({
                'id': trans['id'],
                'item_id': trans['item_id'],
                'entity_id': trans['entity_id'] or trans['item_entity_id'],
                'entity_name': trans['entity_name'] if trans['entity_name'] else None,
                'item_code': trans['item_code'] if trans['item_code'] else 'N/A',
                'item_name': trans['item_name'] if trans['item_name'] else 'Unknown Item',
                'is_credit_item': trans['is_credit_item'] if trans['is_credit_item'] else False,
                'transaction_type': trans['transaction_type'],
                'quantity': float(trans['quantity']) if trans['quantity'] else 0,
                'unit_cost': float(trans['unit_cost']) if trans['unit_cost'] else 0,
                'total_cost': float(trans['total_cost']) if trans['total_cost'] else 0,
                'reference_type': trans['reference_type'],
                'reference_id': trans['reference_id'],
                'reference_info': ref_info,
                'transaction_date': trans['transaction_date'].strftime('%Y-%m-%d %H:%M:%S') if trans['transaction_date'] else '',
                'notes': trans['notes'],
                'performed_by': trans['performed_by'],
                'balance_after': float(trans['balance_after']) if trans['balance_after'] else 0,
                'supplier_name': trans['supplier_name'] if trans['supplier_name'] else '',
                'client_name': trans['client_name'] if trans['client_name'] else ''
            })
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'transactions': transactions_list})
        
    except Exception as e:
        print(f"Error getting inventory transactions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/transactions/add', methods=['POST'])
@perm('inventory.transact')
def add_inventory_transaction():
    """Add a new inventory transaction (purchase, stock_out, adjustment, etc.)
    NOTE: Stock updates are handled by database trigger 'update_inventory_stock_after_transaction'
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        conn, cur = connection()
        
        item_id = data.get('item_id')
        transaction_type = data.get('transaction_type')
        quantity = float(data.get('quantity') or 0)
        unit_cost = float(data.get('unit_cost') or 0)
        total_cost = float(data.get('total_cost') or 0)
        
        if not item_id:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Item ID is required'}), 400
        
        if quantity <= 0:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Quantity must be greater than 0'}), 400
        
        # Define outgoing transaction types (reduce stock)
        outgoing_types = ['sale', 'stock_out', 'credit_out', 'return', 'transfer']
        
        # Get current stock and entity_id to validate outgoing transactions
        cur.execute("SELECT quantity_in_stock, entity_id FROM inventory_items WHERE id = %s", (item_id,))
        item = cur.fetchone()
        if not item:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        
        current_stock = float(item['quantity_in_stock'] or 0)
        item_entity_id = item['entity_id']  # Get entity from item
        
        # Check if we have enough stock for outgoing transactions
        if transaction_type in outgoing_types:
            if quantity > current_stock:
                cur.close()
                conn.close()
                return jsonify({'success': False, 'error': f'Insufficient stock. Available: {current_stock}, Requested: {quantity}'}), 400
        
        # Insert transaction with entity_id - the database trigger handles stock updates and balance_after
        cur.execute("""
            INSERT INTO inventory_transactions
            (item_id, entity_id, transaction_type, quantity, unit_cost, total_cost,
             reference_type, reference_id, supplier_id, client_id, notes, performed_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            item_id,
            item_entity_id,  # Include entity_id from the item
            transaction_type,
            quantity,
            unit_cost,
            total_cost,
            data.get('reference_type'),
            data.get('reference_id'),
            data.get('supplier_id') if data.get('supplier_id') else None,
            data.get('client_id') if data.get('client_id') else None,
            data.get('notes'),
            session.get('username')
        ))
        
        transaction_id = cur.lastrowid
        
        conn.commit()
        
        # Get the new balance after trigger has updated it
        cur.execute("SELECT quantity_in_stock FROM inventory_items WHERE id = %s", (item_id,))
        new_stock = float(cur.fetchone()['quantity_in_stock'] or 0)
        
        cur.close()
        conn.close()
        
        stock_change = new_stock - current_stock
        direction = "reduced by" if stock_change < 0 else "increased by"
        return jsonify({
            'success': True, 
            'transaction_id': transaction_id, 
            'message': f'Transaction recorded. Stock {direction} {abs(stock_change)}. New balance: {new_stock}'
        })
        
    except Exception as e:
        print(f"Error adding inventory transaction: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/credit-items', methods=['GET'])
@perm('inventory.view')
def get_credit_items():
    """Get all credit/consignment items"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        cur.execute("""
            SELECT 
                c.id, c.item_id, c.supplier_id, c.quantity_received, c.quantity_sold,
                c.quantity_returned, c.quantity_remaining, c.agreed_cost_per_item,
                c.total_value, c.payment_due_date, c.payment_status, c.amount_paid,
                c.amount_due, c.received_date, c.due_date, c.settlement_date,
                c.status, c.notes, c.created_by, c.sales_request_item_id,
                i.item_code, i.item_name, i.width, i.height, i.depth, i.unit_of_measure,
                s.supplier_name, s.primary_phone AS contact_mobile,
                CONCAT('SR-', sr.id) as request_number,
                sr.id as request_id,
                cl.client_name as client_name
            FROM inventory_credit_items c
            JOIN inventory_items i ON c.item_id = i.id
            LEFT JOIN supplier s ON c.supplier_id = s.id
            LEFT JOIN sales_request_items sri ON c.sales_request_item_id = sri.id
            LEFT JOIN sales_request sr ON sri.request_id = sr.id
            LEFT JOIN client cl ON sr.client_id = cl.id
            ORDER BY c.received_date DESC
        """)
        credit_items = cur.fetchall()
        
        credit_list = []
        for item in credit_items:
            credit_list.append({
                'id': item['id'],
                'item_id': item['item_id'],
                'item_code': item['item_code'],
                'item_name': item['item_name'],
                'supplier_id': item['supplier_id'],
                'supplier_name': item['supplier_name'] or 'N/A',
                'supplier_mobile': item['contact_mobile'] or '',
                'quantity_received': float(item['quantity_received']) if item['quantity_received'] else 0,
                'quantity_sold': float(item['quantity_sold']) if item['quantity_sold'] else 0,
                'quantity_returned': float(item['quantity_returned']) if item['quantity_returned'] else 0,
                'quantity_remaining': float(item['quantity_remaining']) if item['quantity_remaining'] else 0,
                'agreed_cost_per_item': float(item['agreed_cost_per_item']) if item['agreed_cost_per_item'] else 0,
                'total_value': float(item['total_value']) if item['total_value'] else 0,
                'payment_due_date': item['payment_due_date'].strftime('%Y-%m-%d') if item['payment_due_date'] else '',
                'payment_status': item['payment_status'],
                'amount_paid': float(item['amount_paid']) if item['amount_paid'] else 0,
                'amount_due': float(item['amount_due']) if item['amount_due'] else 0,
                'received_date': item['received_date'].strftime('%Y-%m-%d %H:%M:%S') if item['received_date'] else '',
                'due_date': item['due_date'].strftime('%Y-%m-%d') if item['due_date'] else '',
                'settlement_date': item['settlement_date'].strftime('%Y-%m-%d %H:%M:%S') if item['settlement_date'] else '',
                'status': item['status'],
                'notes': item['notes'],
                'created_by': item['created_by'],
                # NEW: Include dimensions
                'width': float(item['width']) if item['width'] else None,
                'height': float(item['height']) if item['height'] else None,
                'depth': float(item['depth']) if item['depth'] else None,
                'unit_of_measure': item['unit_of_measure'],
                # NEW: Sales request link
                'sales_request_item_id': item['sales_request_item_id'],
                'request_number': item['request_number'],
                'request_id': item['request_id'],
                'client_name': item['client_name']
            })
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'credit_items': credit_list})
        
    except Exception as e:
        print(f"Error getting credit items: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/credit-items/add', methods=['POST'])
@perm('inventory.create')
def add_credit_item():
    """Add a new credit/consignment item - can be linked to sales request or standalone"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        conn, cur = connection()
        
        quantity = float(data.get('quantity_received') or 0)
        cost_per_item = float(data.get('agreed_cost_per_item') or 0)
        total_value = quantity * cost_per_item
        sales_request_item_id = data.get('sales_request_item_id') if data.get('sales_request_item_id') else None
        supplier_id = data.get('supplier_id') if data.get('supplier_id') else None
        
        # Validate required fields
        if quantity <= 0:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Quantity must be greater than 0'}), 400
        
        # Cost is optional - can be 0 or null for some credit items
        
        # Supplier is optional - can be null for some credit items
        
        # Get or create inventory item
        item_id = data.get('item_id')
        
        if not item_id and sales_request_item_id:
            # Create inventory item from sales request item
            cur.execute("""
                SELECT sri.*, sr.id as request_id, sr.title as request_title
                FROM sales_request_items sri
                JOIN sales_request sr ON sri.request_id = sr.id
                WHERE sri.id = %s
            """, (sales_request_item_id,))
            sri = cur.fetchone()
            
            if not sri:
                cur.close()
                conn.close()
                return jsonify({'success': False, 'error': 'Sales request item not found'}), 404
            
            # Parse attributes for dimensions
            attributes = {}
            if sri.get('attributes'):
                try:
                    attributes = json.loads(sri['attributes']) if isinstance(sri['attributes'], str) else sri['attributes']
                except:
                    attributes = {}
            
            # Generate item code
            cur.execute("SELECT MAX(id) as max_id FROM inventory_items")
            max_id = cur.fetchone()['max_id'] or 0
            item_code = f"INV-{max_id + 1:05d}"
            
            item_name = data.get('item_name') or sri.get('name') or 'Credit Item'
            
            # Create the inventory item
            cur.execute("""
                INSERT INTO inventory_items
                (item_code, item_name, item_type, category, unit_of_measure,
                 quantity_in_stock, average_cost, preferred_supplier_id,
                 width, height, depth, sales_request_item_id, is_credit_item, credit_supplier_id, status, created_by)
                VALUES (%s, %s, 'simple', 'Credit Item', %s,
                        %s, %s, %s, %s, %s, %s, %s, 1, %s, 'active', %s)
            """, (
                item_code,
                item_name,
                data.get('unit_type', 'PCS'),
                quantity,
                cost_per_item,
                supplier_id,
                attributes.get('width'),
                attributes.get('height'),
                attributes.get('depth'),
                sales_request_item_id,
                supplier_id,
                session.get('username')
            ))
            
            item_id = cur.lastrowid
            print(f"Created new inventory item {item_id} for credit item from sales request item {sales_request_item_id}")
            
        elif not item_id:
            # Create a NEW inventory item WITHOUT sales request (standalone credit item)
            item_name = data.get('item_name', '').strip()
            item_code = data.get('item_code', '').strip()
            
            if not item_name:
                cur.close()
                conn.close()
                return jsonify({'success': False, 'error': 'Item name is required'}), 400
            
            # Auto-generate item code if not provided
            if not item_code:
                cur.execute("SELECT MAX(id) as max_id FROM inventory_items")
                max_id = cur.fetchone()['max_id'] or 0
                item_code = f"CRD-{max_id + 1:05d}"
            
            # Check for duplicate item code
            cur.execute("SELECT id FROM inventory_items WHERE item_code = %s", (item_code,))
            if cur.fetchone():
                cur.close()
                conn.close()
                return jsonify({'success': False, 'error': f'Item code {item_code} already exists'}), 400
            
            # Create the inventory item
            cur.execute("""
                INSERT INTO inventory_items
                (item_code, item_name, item_type, category, unit_of_measure,
                 quantity_in_stock, average_cost, preferred_supplier_id,
                 width, height, depth, is_credit_item, credit_supplier_id, status, created_by)
                VALUES (%s, %s, 'simple', 'Credit Item', %s,
                        %s, %s, %s, %s, %s, %s, 1, %s, 'active', %s)
            """, (
                item_code,
                item_name,
                data.get('unit_type', 'PCS'),
                quantity,
                cost_per_item,
                supplier_id,
                data.get('width'),
                data.get('height'),
                data.get('depth'),
                supplier_id,
                session.get('username')
            ))
            
            item_id = cur.lastrowid
            print(f"Created new standalone credit inventory item {item_id}: {item_name}")
        
        if not item_id:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'No inventory item specified or created'}), 400
        
        # Insert credit item
        cur.execute("""
            INSERT INTO inventory_credit_items
            (item_id, supplier_id, quantity_received, quantity_remaining,
             agreed_cost_per_item, total_value, payment_due_date, due_date,
             amount_due, notes, created_by, sales_request_item_id, received_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            item_id,
            supplier_id,
            quantity,
            quantity,
            cost_per_item,
            total_value,
            data.get('payment_due_date'),
            data.get('due_date') or data.get('payment_due_date'),
            total_value,  # Amount due = total value initially
            data.get('notes'),
            session.get('username'),
            sales_request_item_id,
            data.get('received_date') or datetime.now().strftime('%Y-%m-%d')
        ))
        
        credit_item_id = cur.lastrowid
        
        # NOTE: Do NOT manually insert into inventory_transactions here
        # The database has a trigger that automatically creates a transaction
        # when a credit item is inserted or when inventory_items are updated
        # Manual insertion causes error: "Can't update table in trigger"
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'credit_item_id': credit_item_id, 
            'item_id': item_id,
            'message': 'Credit item added successfully'
        })
        
    except Exception as e:
        print(f"Error adding credit item: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/credit-items/<int:credit_id>', methods=['GET'])
@perm('inventory.view')
def get_credit_item(credit_id):
    """Get a single credit item by ID with its transactions"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Get credit item details
        cur.execute("""
            SELECT 
                c.id, c.item_id, c.supplier_id, c.quantity_received, c.quantity_sold,
                c.quantity_returned, c.quantity_remaining, c.agreed_cost_per_item,
                c.total_value, c.payment_due_date, c.payment_status, c.amount_paid,
                c.amount_due, c.received_date, c.due_date, c.settlement_date,
                c.status, c.notes, c.created_by, c.sales_request_item_id,
                i.item_code, i.item_name, i.width, i.height, i.depth, i.unit_of_measure,
                s.supplier_name, s.primary_phone AS contact_mobile,
                CONCAT('SR-', sr.id) as request_number,
                sr.id as request_id,
                cl.client_name as client_name
            FROM inventory_credit_items c
            JOIN inventory_items i ON c.item_id = i.id
            LEFT JOIN supplier s ON c.supplier_id = s.id
            LEFT JOIN sales_request_items sri ON c.sales_request_item_id = sri.id
            LEFT JOIN sales_request sr ON sri.request_id = sr.id
            LEFT JOIN client cl ON sr.client_id = cl.id
            WHERE c.id = %s
        """, (credit_id,))
        
        item = cur.fetchone()
        
        if not item:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Credit item not found'}), 404
        
        # Get transactions for this credit item's inventory item
        cur.execute("""
            SELECT 
                t.id, t.transaction_type, t.quantity, t.unit_cost, t.total_cost,
                t.transaction_date, t.notes, t.performed_by, t.balance_after,
                t.reference_type, t.reference_id
            FROM inventory_transactions t
            WHERE t.item_id = %s
            ORDER BY t.transaction_date DESC
            LIMIT 50
        """, (item['item_id'],))
        transactions = cur.fetchall()
        
        trans_list = []
        for trans in transactions:
            trans_list.append({
                'id': trans['id'],
                'transaction_type': trans['transaction_type'],
                'quantity': float(trans['quantity']) if trans['quantity'] else 0,
                'unit_cost': float(trans['unit_cost']) if trans['unit_cost'] else 0,
                'total_cost': float(trans['total_cost']) if trans['total_cost'] else 0,
                'transaction_date': trans['transaction_date'].strftime('%Y-%m-%d %H:%M') if trans['transaction_date'] else '',
                'notes': trans['notes'],
                'performed_by': trans['performed_by'],
                'balance_after': float(trans['balance_after']) if trans['balance_after'] else 0
            })
        
        cur.close()
        conn.close()
        
        credit_data = {
            'id': item['id'],
            'item_id': item['item_id'],
            'item_code': item['item_code'],
            'item_name': item['item_name'],
            'supplier_id': item['supplier_id'],
            'supplier_name': item['supplier_name'] or 'N/A',
            'supplier_mobile': item['contact_mobile'] or '',
            'quantity_received': float(item['quantity_received']) if item['quantity_received'] else 0,
            'quantity_sold': float(item['quantity_sold']) if item['quantity_sold'] else 0,
            'quantity_returned': float(item['quantity_returned']) if item['quantity_returned'] else 0,
            'quantity_remaining': float(item['quantity_remaining']) if item['quantity_remaining'] else 0,
            'agreed_cost_per_item': float(item['agreed_cost_per_item']) if item['agreed_cost_per_item'] else 0,
            'total_value': float(item['total_value']) if item['total_value'] else 0,
            'payment_due_date': item['payment_due_date'].strftime('%Y-%m-%d') if item['payment_due_date'] else '',
            'payment_status': item['payment_status'],
            'amount_paid': float(item['amount_paid']) if item['amount_paid'] else 0,
            'amount_due': float(item['amount_due']) if item['amount_due'] else 0,
            'received_date': item['received_date'].strftime('%Y-%m-%d') if item['received_date'] else '',
            'status': item['status'],
            'notes': item['notes'],
            'width': float(item['width']) if item['width'] else None,
            'height': float(item['height']) if item['height'] else None,
            'depth': float(item['depth']) if item['depth'] else None,
            'unit_of_measure': item['unit_of_measure'],
            'sales_request_item_id': item['sales_request_item_id'],
            'request_id': item['request_id'],
            'request_number': item['request_number'],
            'client_name': item['client_name'],
            'transactions': trans_list
        }
        
        return jsonify({'success': True, 'item': credit_data})
        
    except Exception as e:
        print(f"Error getting credit item: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/credit-items/<int:credit_id>/add-quantity', methods=['POST'])
@perm('inventory.transact')
def add_quantity_to_credit_item(credit_id):
    """Add more quantity to an existing credit item"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        conn, cur = connection()
        
        quantity_to_add = float(data.get('quantity') or 0)
        cost_per_item = float(data.get('cost_per_item') or 0)
        notes = data.get('notes', '')
        
        if quantity_to_add <= 0:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Quantity must be greater than 0'}), 400
        
        # Get existing credit item
        cur.execute("""
            SELECT c.*, i.item_name, i.item_code
            FROM inventory_credit_items c
            JOIN inventory_items i ON c.item_id = i.id
            WHERE c.id = %s
        """, (credit_id,))
        credit_item = cur.fetchone()
        
        if not credit_item:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Credit item not found'}), 404
        
        # Use existing cost if not provided
        if cost_per_item <= 0:
            cost_per_item = float(credit_item['agreed_cost_per_item'] or 0)
        
        additional_value = quantity_to_add * cost_per_item
        
        # Update the credit item quantities
        new_quantity_received = float(credit_item['quantity_received']) + quantity_to_add
        new_quantity_remaining = float(credit_item['quantity_remaining']) + quantity_to_add
        new_total_value = float(credit_item['total_value'] or 0) + additional_value
        new_amount_due = float(credit_item['amount_due'] or 0) + additional_value
        
        cur.execute("""
            UPDATE inventory_credit_items
            SET quantity_received = %s,
                quantity_remaining = %s,
                total_value = %s,
                amount_due = %s
            WHERE id = %s
        """, (new_quantity_received, new_quantity_remaining, new_total_value, new_amount_due, credit_id))
        
        # Record a credit_in transaction - DB trigger will update inventory_items.quantity_in_stock
        cur.execute("""
            INSERT INTO inventory_transactions
            (item_id, transaction_type, quantity, unit_cost, total_cost,
             reference_type, reference_id, supplier_id, notes, performed_by)
            VALUES (%s, 'credit_in', %s, %s, %s, 'credit_item', %s, %s, %s, %s)
        """, (
            credit_item['item_id'],
            quantity_to_add,
            cost_per_item,
            additional_value,
            credit_id,
            credit_item['supplier_id'],
            f"Added {quantity_to_add} more to credit item. {notes}",
            session.get('username')
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Added {quantity_to_add} units to {credit_item["item_name"]}',
            'new_quantity_received': new_quantity_received,
            'new_quantity_remaining': new_quantity_remaining
        })
        
    except Exception as e:
        print(f"Error adding quantity to credit item: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/credit-items/<int:credit_id>/sell', methods=['POST'])
@perm('inventory.transact')
def sell_credit_item(credit_id):
    """Record sale of credit item"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        conn, cur = connection()
        
        # Get credit item details
        cur.execute("SELECT * FROM inventory_credit_items WHERE id = %s", (credit_id,))
        credit_item = cur.fetchone()
        
        if not credit_item:
            return jsonify({'success': False, 'error': 'Credit item not found'}), 404
        
        quantity_sold = float(data.get('quantity'))
        
        if quantity_sold > credit_item['quantity_remaining']:
            return jsonify({'success': False, 'error': 'Insufficient quantity remaining'}), 400
        
        # Update credit item quantities
        new_sold = float(credit_item['quantity_sold'] or 0) + quantity_sold
        new_remaining = float(credit_item['quantity_remaining']) - quantity_sold
        
        cur.execute("""
            UPDATE inventory_credit_items
            SET quantity_sold = %s,
                quantity_remaining = %s
            WHERE id = %s
        """, (new_sold, new_remaining, credit_id))
        
        # Record transaction - DB trigger handles inventory_items.quantity_in_stock
        cur.execute("""
            INSERT INTO inventory_transactions
            (item_id, transaction_type, quantity, unit_cost, total_cost,
             reference_type, reference_id, client_id, notes, performed_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            credit_item['item_id'],
            'credit_out',
            quantity_sold,
            credit_item['agreed_cost_per_item'],
            quantity_sold * float(credit_item['agreed_cost_per_item'] or 0),
            'credit_supplier',
            credit_id,
            data.get('client_id'),
            data.get('notes'),
            session.get('username')
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Sale recorded successfully'})
        
    except Exception as e:
        print(f"Error selling credit item: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/credit-items/<int:credit_id>/return', methods=['POST'])
@perm('inventory.transact')
def return_credit_item(credit_id):
    """Return unsold credit items to supplier"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        conn, cur = connection()
        
        # Get credit item details
        cur.execute("SELECT * FROM inventory_credit_items WHERE id = %s", (credit_id,))
        credit_item = cur.fetchone()
        
        if not credit_item:
            return jsonify({'success': False, 'error': 'Credit item not found'}), 404
        
        quantity_returned = float(data.get('quantity'))
        
        if quantity_returned > credit_item['quantity_remaining']:
            return jsonify({'success': False, 'error': 'Cannot return more than remaining quantity'}), 400
        
        # Update credit item quantities
        new_returned = float(credit_item['quantity_returned'] or 0) + quantity_returned
        new_remaining = float(credit_item['quantity_remaining']) - quantity_returned
        
        cur.execute("""
            UPDATE inventory_credit_items
            SET quantity_returned = %s,
                quantity_remaining = %s
            WHERE id = %s
        """, (new_returned, new_remaining, credit_id))
        
        # Record transaction - use 'return' type (reduces stock via trigger)
        cur.execute("""
            INSERT INTO inventory_transactions
            (item_id, transaction_type, quantity, unit_cost, total_cost,
             reference_type, reference_id, supplier_id, notes, performed_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            credit_item['item_id'],
            'return',
            quantity_returned,
            credit_item['agreed_cost_per_item'],
            0,
            'credit_return',
            credit_id,
            credit_item['supplier_id'],
            data.get('notes', 'Returned to supplier'),
            session.get('username')
        ))
        
        # Check if fully returned
        if new_remaining == 0:
            cur.execute("UPDATE inventory_credit_items SET status = 'returned' WHERE id = %s", (credit_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Return recorded successfully'})
        
    except Exception as e:
        print(f"Error returning credit item: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/credit-items/<int:credit_id>/payment', methods=['POST'])
@perm('inventory.transact')
def record_credit_payment(credit_id):
    """Record payment for credit item"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        conn, cur = connection()
        
        # Get credit item details
        cur.execute("SELECT * FROM inventory_credit_items WHERE id = %s", (credit_id,))
        credit_item = cur.fetchone()
        
        if not credit_item:
            return jsonify({'success': False, 'error': 'Credit item not found'}), 404
        
        payment_amount = float(data.get('payment_amount'))
        new_amount_paid = credit_item['amount_paid'] + payment_amount
        new_amount_due = credit_item['amount_due'] - payment_amount
        
        # Update payment status
        payment_status = 'paid' if new_amount_due <= 0 else 'partial' if new_amount_paid > 0 else 'pending'
        settlement_date = datetime.now() if payment_status == 'paid' else None
        
        cur.execute("""
            UPDATE inventory_credit_items
            SET amount_paid = %s, amount_due = %s, payment_status = %s, settlement_date = %s
            WHERE id = %s
        """, (new_amount_paid, new_amount_due, payment_status, settlement_date, credit_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Payment recorded successfully'})
        
    except Exception as e:
        print(f"Error recording credit payment: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/approved-items', methods=['GET'])
@perm('inventory.view')
def get_approved_items_from_sales():
    """Get approved items from sales requests that can be added to inventory"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Get approved items with costing, selling price, and client approval
        cur.execute("""
            SELECT 
                sri.id as sales_item_id,
                sri.request_id as sales_request_id,
                CONCAT('SR-', sr.id) as request_number,
                c.client_name,
                comp.company_name,
                sri.name as item_name,
                sri.qty as quantity,
                sri.cost_per_item,
                sri.sell_per_item,
                (COALESCE(sri.sell_per_item, 0) - COALESCE(sri.cost_per_item, 0)) as expected_profit_per_unit,
                sri.approval_status as client_approval_status,
                sri.client_approval_date,
                COALESCE(
                    JSON_UNQUOTE(JSON_EXTRACT(sri.attributes, '$.width')),
                    NULL
                ) as width,
                COALESCE(
                    JSON_UNQUOTE(JSON_EXTRACT(sri.attributes, '$.height')),
                    NULL
                ) as height,
                COALESCE(
                    JSON_UNQUOTE(JSON_EXTRACT(sri.attributes, '$.depth')),
                    NULL
                ) as depth,
                sri.unit,
                sri.item_type as request_type,
                sri.description,
                JSON_UNQUOTE(JSON_EXTRACT(sri.attributes, '$.specifications')) as specifications,
                JSON_UNQUOTE(JSON_EXTRACT(sri.attributes, '$.notes')) as notes,
                sri.inventory_item_id,
                ii.item_code as inventory_item_code,
                CASE WHEN sri.inventory_item_id IS NOT NULL THEN TRUE ELSE FALSE END as already_in_inventory
            FROM sales_request_items sri
            JOIN sales_request sr ON sri.request_id = sr.id
            LEFT JOIN client c ON sr.client_id = c.id
            LEFT JOIN company comp ON sr.company_id = comp.id
            LEFT JOIN inventory_items ii ON sri.inventory_item_id = ii.id
            WHERE sri.approval_status = 'approved'
              AND sri.cost_per_item IS NOT NULL 
              AND sri.cost_per_item > 0
              AND sri.sell_per_item IS NOT NULL 
              AND sri.sell_per_item > 0
              AND sri.client_approval_date IS NOT NULL
            ORDER BY sri.client_approval_date DESC
        """)
        approved_items = cur.fetchall()
        
        items_list = []
        for item in approved_items:
            items_list.append({
                'sales_item_id': item['sales_item_id'],
                'sales_request_id': item['sales_request_id'],
                'request_number': item['request_number'],
                'client_name': item['client_name'],
                'company_name': item['company_name'] if item['company_name'] else '',
                'item_name': item['item_name'],
                'quantity': float(item['quantity']) if item['quantity'] else 0,
                'cost_per_item': float(item['cost_per_item']) if item['cost_per_item'] else 0,
                'sell_per_item': float(item['sell_per_item']) if item['sell_per_item'] else 0,
                'expected_profit_per_unit': float(item['expected_profit_per_unit']) if item['expected_profit_per_unit'] else 0,
                'total_profit': float(item['expected_profit_per_unit']) * float(item['quantity']) if item['expected_profit_per_unit'] and item['quantity'] else 0,
                'approval_date': item['client_approval_date'].strftime('%Y-%m-%d %H:%M:%S') if item['client_approval_date'] else '',
                'already_in_inventory': bool(item['already_in_inventory']),
                'inventory_item_id': item['inventory_item_id'] if item['inventory_item_id'] else None,
                'inventory_item_code': item['inventory_item_code'] if item.get('inventory_item_code') else None,
                # NEW: Include dimensions and specifications
                'width': float(item['width']) if item['width'] else None,
                'height': float(item['height']) if item['height'] else None,
                'depth': float(item['depth']) if item['depth'] else None,
                'unit': item['unit'],
                'request_type': item['request_type'],
                'description': item['description'],
                'specifications': item['specifications'],
                'notes': item['notes']
            })
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'approved_items': items_list})
        
    except Exception as e:
        print(f"Error getting approved items: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/items/create-from-sales', methods=['POST'])
@perm('inventory.create')
def create_inventory_from_sales():
    """
    Smart inventory management from sales requests:
    - Supports creating REGULAR or CREDIT inventory items
    - Checks if item already exists (by name + unit + dimensions)
    - If exists: Updates stock or adds as credit item
    - If new: Creates new inventory item with proper is_credit_item flag
    - Always creates transaction record
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json() or {}
    sales_item_id = data.get('sales_item_id')
    inventory_type = data.get('inventory_type', 'regular')  # 'regular' or 'credit'
    supplier_id = data.get('supplier_id')  # Optional - can be specified for both types
    
    if not sales_item_id:
        return jsonify({'success': False, 'error': 'Missing sales_item_id'}), 400

    # Validate inventory_type
    if inventory_type not in ['regular', 'credit']:
        return jsonify({'success': False, 'error': 'Invalid inventory_type. Must be "regular" or "credit"'}), 400

    # For credit items, supplier is now optional - they primarily link to sales request
    # Supplier can be specified but is not required

    try:
        conn, cur = connection()

        # Fetch the sales item and its parent request
        cur.execute("""
            SELECT sri.*, sr.client_id, sr.company_id 
            FROM sales_request_items sri 
            JOIN sales_request sr ON sri.request_id = sr.id 
            WHERE sri.id = %s
        """, (sales_item_id,))
        sales_item = cur.fetchone()
        
        if not sales_item:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Sales item not found'}), 404

        # Ensure item is approved
        if sales_item.get('approval_status') != 'approved':
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Sales item is not approved'}), 400

        # Extract dimensions from sales item attributes
        width = None
        height = None
        depth = None
        specifications = None
        try:
            attrs = json.loads(sales_item.get('attributes') or '{}') if sales_item.get('attributes') else {}
            width = attrs.get('width')
            height = attrs.get('height')
            depth = attrs.get('depth')
            specifications = attrs.get('specifications')
        except Exception:
            pass

        item_name = sales_item.get('name') or sales_item.get('item_name') or 'Unnamed Item'
        unit_of_measure = sales_item.get('unit') or 'PCS'
        quantity = float(sales_item.get('qty') or 0)
        unit_cost = float(sales_item.get('cost_per_item') or 0)
        unit_selling_price = float(sales_item.get('sell_per_item') or 0)
        
        # Determine flags based on inventory_type
        is_credit_item = (inventory_type == 'credit')

        # ========================================
        # SMART INVENTORY LOGIC: Check if item already exists in the SAME inventory type
        # Regular and Credit inventory are separate - same item can exist in both
        # ========================================
        cur.execute("""
            SELECT id, item_code, quantity_in_stock, average_cost, is_credit_item
            FROM inventory_items
            WHERE item_name = %s 
              AND unit_of_measure = %s
              AND COALESCE(width, 0) = COALESCE(%s, 0)
              AND COALESCE(height, 0) = COALESCE(%s, 0)
              AND COALESCE(depth, 0) = COALESCE(%s, 0)
              AND is_credit_item = %s
              AND status = 'active'
            LIMIT 1
        """, (item_name, unit_of_measure, width, height, depth, is_credit_item))
        
        existing_item = cur.fetchone()

        if existing_item:
            # ========================================
            # ITEM EXISTS in this inventory type - Add transaction to existing item
            # ========================================
            inventory_item_id = existing_item['id']
            item_code = existing_item['item_code']
            
            if inventory_type == 'credit':
                # Add as credit item (linked to sales request, supplier optional)
                credit_notes = f'Credit item from sales request #{sales_item.get("request_id")}'
                if not supplier_id:
                    credit_notes += ' (No supplier - linked to sales request only)'
                
                cur.execute("""
                    INSERT INTO inventory_credit_items
                    (item_id, supplier_id, quantity_received, quantity_remaining,
                     agreed_cost_per_item, total_value, payment_status, status,
                     created_by, sales_request_item_id, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending', 'active', %s, %s, %s)
                """, (
                    inventory_item_id,
                    supplier_id if supplier_id else None,
                    quantity,
                    quantity,
                    unit_cost,
                    quantity * unit_cost,
                    session.get('username'),
                    sales_item_id,
                    credit_notes
                ))
                credit_item_id = cur.lastrowid
                
                # Create credit_in transaction
                transaction_notes = f'Credit item from Sales Request Item #{sales_item_id}'
                if supplier_id:
                    transaction_notes = f'Credit received from supplier - {transaction_notes}'
                else:
                    transaction_notes = f'Credit linked to sales request - {transaction_notes}'
                
                cur.execute("""
                    INSERT INTO inventory_transactions
                    (item_id, transaction_type, quantity, unit_cost, total_cost,
                     reference_type, reference_id, supplier_id, notes, performed_by)
                    VALUES (%s, 'credit_in', %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    inventory_item_id,
                    quantity,
                    unit_cost,
                    quantity * unit_cost,
                    'sales_request' if not supplier_id else 'credit_supplier',
                    sales_item_id if not supplier_id else credit_item_id,
                    supplier_id if supplier_id else None,
                    transaction_notes,
                    session.get('username')
                ))
                
                message = f'Added {quantity} units as credit item to existing inventory'
            else:
                # Add to regular stock via purchase transaction
                cur.execute("""
                    INSERT INTO inventory_transactions
                    (item_id, transaction_type, quantity, unit_cost, total_cost,
                     reference_type, reference_id, notes, performed_by)
                    VALUES (%s, 'purchase', %s, %s, %s, 'sales_request', %s, %s, %s)
                """, (
                    inventory_item_id,
                    quantity,
                    unit_cost,
                    quantity * unit_cost,
                    sales_item_id,
                    f'Stock added from approved sales request item #{sales_item_id}',
                    session.get('username')
                ))
                
                message = f'Added {quantity} units to existing inventory item'
            
            # Link sales item to inventory item
            cur.execute("""
                UPDATE sales_request_items 
                SET inventory_item_id = %s 
                WHERE id = %s
            """, (inventory_item_id, sales_item_id))
            
            # Update parent sales request status to indicate it's now in progress
            cur.execute("""
                UPDATE sales_request 
                SET status = 'in_progress' 
                WHERE id = %s AND status != 'completed'
            """, (sales_item.get('request_id'),))
            
            conn.commit()
            cur.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'action': 'updated_existing',
                'message': message,
                'inventory_item_id': inventory_item_id,
                'item_code': item_code,
                'is_credit': is_credit_item,
                'item_id': inventory_item_id
            })
        
        else:
            # ========================================
            # NEW ITEM - Create inventory item with proper is_credit_item flag
            # ========================================
            
            # Generate item code
            cur.execute("SELECT COALESCE(MAX(id), 0) as maxid FROM inventory_items")
            row = cur.fetchone()
            next_id = (row.get('maxid') or 0) + 1
            item_code = f"INV-{str(next_id).zfill(5)}"

            category = data.get('category') or sales_item.get('item_type') or 'General'
            minimum_stock_level = int(data.get('minimum_stock_level') or 10)
            reorder_level = int(data.get('reorder_level') or 20)
            expected_profit_per_unit = unit_selling_price - unit_cost if unit_selling_price and unit_cost else 0

            # Create new inventory item with ZERO initial quantity
            # The transaction will update the stock via trigger
            # Set is_credit_item and credit_supplier_id based on inventory_type
            cur.execute("""
                INSERT INTO inventory_items
                (item_code, item_name, item_type, category, description, unit_of_measure,
                 quantity_in_stock, minimum_stock_level, reorder_level, average_cost,
                 preferred_supplier_id, credit_supplier_id, is_credit_item,
                 source_type, status, created_by,
                 sales_request_item_id, unit_selling_price, expected_profit_per_unit,
                 width, height, depth, specifications)
                VALUES (%s, %s, 'simple', %s, %s, %s, 0, %s, %s, %s, %s, %s, %s, 'sales_request', 'active', %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                item_code, item_name, category,
                sales_item.get('description'),
                unit_of_measure,
                minimum_stock_level, reorder_level, unit_cost,
                supplier_id if inventory_type == 'regular' else None,
                supplier_id if inventory_type == 'credit' else None,
                is_credit_item,
                session.get('username'),
                sales_item_id, unit_selling_price, expected_profit_per_unit,
                width, height, depth, specifications
            ))

            inventory_item_id = cur.lastrowid

            # Create initial transaction record - trigger will update stock
            # Handle both regular purchases (with or without supplier) and credit items
            if inventory_type == 'credit':
                credit_notes = f'Initial credit item from sales request #{sales_item_id}'
                if not supplier_id:
                    credit_notes += ' (linked to sales request only)'
                
                cur.execute("""
                    INSERT INTO inventory_transactions
                    (item_id, transaction_type, quantity, unit_cost, total_cost,
                     reference_type, reference_id, supplier_id, notes, performed_by)
                    VALUES (%s, 'credit_in', %s, %s, %s, 'sales_request', %s, %s, %s, %s)
                """, (
                    inventory_item_id,
                    quantity, unit_cost, quantity * unit_cost,
                    sales_item_id,
                    supplier_id if supplier_id else None,
                    credit_notes,
                    session.get('username')
                ))
            else:
                cur.execute("""
                    INSERT INTO inventory_transactions
                    (item_id, transaction_type, quantity, unit_cost, total_cost,
                     reference_type, reference_id, supplier_id, notes, performed_by)
                    VALUES (%s, 'purchase', %s, %s, %s, 'sales_request', %s, %s, %s, %s)
                """, (
                    inventory_item_id,
                    quantity, unit_cost, quantity * unit_cost,
                    sales_item_id,
                    supplier_id if supplier_id else None,
                    f'Initial stock from sales request item #{sales_item_id}',
                    session.get('username')
                ))

            # If credit item, create credit record
            if inventory_type == 'credit':
                credit_item_notes = f'Initial credit item from sales request #{sales_item.get("request_id")}'
                if not supplier_id:
                    credit_item_notes += ' (No supplier - linked to sales request only)'
                
                cur.execute("""
                    INSERT INTO inventory_credit_items
                    (item_id, supplier_id, quantity_received, quantity_remaining,
                     agreed_cost_per_item, total_value, payment_status, status,
                     created_by, sales_request_item_id, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending', 'active', %s, %s, %s)
                """, (
                    inventory_item_id, 
                    supplier_id if supplier_id else None, 
                    quantity, quantity,
                    unit_cost, quantity * unit_cost,
                    session.get('username'), sales_item_id,
                    credit_item_notes
                ))

            # Link sales item to inventory item
            cur.execute("""
                UPDATE sales_request_items 
                SET inventory_item_id = %s 
                WHERE id = %s
            """, (inventory_item_id, sales_item_id))

            # Update parent sales request status to indicate it's now in progress
            cur.execute("""
                UPDATE sales_request 
                SET status = 'in_progress' 
                WHERE id = %s AND status != 'completed'
            """, (sales_item.get('request_id'),))

            conn.commit()
            cur.close()
            conn.close()

            return jsonify({
                'success': True,
                'action': 'created_new',
                'message': f'New {inventory_type} inventory item created with {quantity} units',
                'inventory_item_id': inventory_item_id,
                'item_id': inventory_item_id,
                'item_code': item_code,
                'inventory_type': inventory_type,
                'is_credit_item': is_credit_item
            })

    except Exception as e:
        try:
            conn.rollback()
            cur.close()
            conn.close()
        except Exception:
            pass
        print(f"Error in smart inventory management: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/alerts', methods=['GET'])
@perm('inventory.view')
def get_inventory_alerts():
    """Get all unresolved inventory alerts - filtered by entity or credit"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Get filter params
        entity_id = request.args.get('entity_id')
        inventory_type = request.args.get('inventory_type')  # 'credit' or None
        
        query = """
            SELECT 
                a.id, a.item_id, a.entity_id, a.alert_type, a.alert_message, a.severity,
                a.created_at,
                i.item_code, i.item_name, i.quantity_in_stock, i.is_credit_item,
                e.entity_name
            FROM inventory_alerts a
            JOIN inventory_items i ON a.item_id = i.id
            LEFT JOIN entities e ON a.entity_id = e.id
            WHERE a.is_resolved = FALSE
        """
        params = []
        
        # Filter by entity for regular inventory
        if entity_id:
            query += " AND a.entity_id = %s"
            params.append(entity_id)
        # Filter credit items only
        elif inventory_type == 'credit':
            query += " AND i.is_credit_item = TRUE"
        
        query += """
            ORDER BY 
                CASE a.severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                a.created_at DESC
        """
        
        cur.execute(query, params)
        alerts = cur.fetchall()
        
        alerts_list = []
        for alert in alerts:
            alerts_list.append({
                'id': alert['id'],
                'item_id': alert['item_id'],
                'entity_id': alert['entity_id'],
                'entity_name': alert['entity_name'],
                'item_code': alert['item_code'],
                'item_name': alert['item_name'],
                'quantity_in_stock': float(alert['quantity_in_stock']) if alert['quantity_in_stock'] else 0,
                'is_credit_item': alert['is_credit_item'] if alert['is_credit_item'] else False,
                'alert_type': alert['alert_type'],
                'alert_message': alert['alert_message'],
                'severity': alert['severity'],
                'created_at': alert['created_at'].strftime('%Y-%m-%d %H:%M:%S') if alert['created_at'] else ''
            })
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'alerts': alerts_list})
        
    except Exception as e:
        print(f"Error getting inventory alerts: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/alerts/<int:alert_id>/resolve', methods=['POST'])
@perm('inventory.transact')
def resolve_inventory_alert(alert_id):
    """Mark an inventory alert as resolved"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        cur.execute("""
            UPDATE inventory_alerts
            SET is_resolved = TRUE, resolved_at = NOW(), resolved_by = %s
            WHERE id = %s
        """, (session.get('username'), alert_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Alert resolved'})
        
    except Exception as e:
        print(f"Error resolving alert: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/statistics', methods=['GET'])
@perm('inventory.view')
def get_inventory_statistics():
    """Get inventory statistics for dashboard with regular/credit separation"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Total items - separated by type
        cur.execute("SELECT COUNT(*) as count FROM inventory_items WHERE status = 'active' AND is_credit_item = FALSE")
        regular_items = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM inventory_items WHERE status = 'active' AND is_credit_item = TRUE")
        credit_items = cur.fetchone()['count']
        
        total_items = regular_items + credit_items
        
        # Low stock items - both types
        cur.execute("""
            SELECT COUNT(*) as count FROM inventory_items 
            WHERE status = 'active' AND quantity_in_stock <= minimum_stock_level
        """)
        low_stock_items = cur.fetchone()['count']
        
        # Out of stock items - both types
        cur.execute("""
            SELECT COUNT(*) as count FROM inventory_items 
            WHERE status = 'active' AND quantity_in_stock = 0
        """)
        out_of_stock_items = cur.fetchone()['count']
        
        # Total inventory value - both types
        cur.execute("""
            SELECT SUM(quantity_in_stock * average_cost) as total_value
            FROM inventory_items WHERE status = 'active'
        """)
        total_value = cur.fetchone()['total_value'] or 0
        
        # Active credit items (from credit_items table)
        cur.execute("SELECT COUNT(*) as count FROM inventory_credit_items WHERE status = 'active'")
        active_credit_records = cur.fetchone()['count']
        
        # Total credit amount due
        cur.execute("""
            SELECT SUM(amount_due) as total_due
            FROM inventory_credit_items WHERE status = 'active'
        """)
        total_credit_due = cur.fetchone()['total_due'] or 0
        
        # Unresolved alerts
        cur.execute("SELECT COUNT(*) as count FROM inventory_alerts WHERE is_resolved = FALSE")
        unresolved_alerts = cur.fetchone()['count']
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'regular_items': regular_items,
            'credit_items': credit_items,
            'total_items': total_items,
            'low_stock': low_stock_items,
            'out_of_stock': out_of_stock_items,
            'total_value': float(total_value),
            'active_credit_records': active_credit_records,
            'total_credit_due': float(total_credit_due),
            'unresolved_alerts': unresolved_alerts,
            # Legacy fields for backward compatibility
            'statistics': {
                'total_items': total_items,
                'low_stock_items': low_stock_items,
                'out_of_stock_items': out_of_stock_items,
                'total_inventory_value': float(total_value),
                'active_credit_items': active_credit_records,
                'total_credit_due': float(total_credit_due),
                'unresolved_alerts': unresolved_alerts
            }
        })
        
    except Exception as e:
        print(f"Error getting inventory statistics: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# END ITEM MANAGEMENT & INVENTORY SYSTEM
# ============================================================================

# ============================================================================
# FINANCE MODULE - Payment Methods, Categories, Transactions, Approvals
# ============================================================================

# ----------------------- PAYMENT METHODS -----------------------

@app.route('/api/finance/payment-methods', methods=['GET'])
@perm('finance_master.view')
def get_payment_methods():
    """Get all payment methods with current balances"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        cur.execute("""
            SELECT id, method_name, method_code, description, account_number, 
                   bank_name, current_balance, opening_balance, is_active, 
                   display_order, created_at
            FROM payment_methods 
            ORDER BY display_order, method_name
        """)
        methods = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'payment_methods': [{
                'id': m['id'],
                'method_name': m['method_name'],
                'method_code': m['method_code'],
                'description': m['description'],
                'account_number': m['account_number'],
                'bank_name': m['bank_name'],
                'current_balance': float(m['current_balance'] or 0),
                'opening_balance': float(m['opening_balance'] or 0),
                'is_active': bool(m['is_active']),
                'display_order': m['display_order']
            } for m in methods]
        })
    except Exception as e:
        print(f"Error getting payment methods: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/payment-methods', methods=['POST'])
@perm('finance_master.edit')
def add_payment_method():
    """Add a new payment method"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        method_name = data.get('method_name', '').strip()
        method_code = data.get('method_code', '').strip().upper()
        description = data.get('description', '')
        account_number = data.get('account_number', '')
        bank_name = data.get('bank_name', '')
        opening_balance = float(data.get('opening_balance', 0))
        
        if not method_name or not method_code:
            return jsonify({'success': False, 'error': 'Method name and code are required'}), 400
        
        conn, cur = connection()
        
        # Check for duplicate code
        cur.execute("SELECT id FROM payment_methods WHERE method_code = %s", (method_code,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Payment method code already exists'}), 400
        
        cur.execute("""
            INSERT INTO payment_methods 
            (method_name, method_code, description, account_number, bank_name, 
             opening_balance, current_balance, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (method_name, method_code, description, account_number, bank_name,
              opening_balance, opening_balance, session.get('user_name')))
        
        method_id = cur.lastrowid
        
        # Record opening balance in history
        if opening_balance > 0:
            cur.execute("""
                INSERT INTO payment_method_balance_history
                (payment_method_id, previous_balance, change_amount, new_balance, 
                 change_type, description, created_by)
                VALUES (%s, 0, %s, %s, 'opening_balance', 'Initial opening balance', %s)
            """, (method_id, opening_balance, opening_balance, session.get('user_name')))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Payment method added', 'id': method_id})
    except Exception as e:
        print(f"Error adding payment method: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/payment-methods/<int:method_id>', methods=['PUT'])
@perm('finance_master.edit')
def update_payment_method(method_id):
    """Update a payment method"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        conn, cur = connection()
        
        # Get current method data
        cur.execute("SELECT * FROM payment_methods WHERE id = %s", (method_id,))
        method = cur.fetchone()
        if not method:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Payment method not found'}), 404
        
        method_name = data.get('method_name', method['method_name'])
        description = data.get('description', method['description'])
        account_number = data.get('account_number', method['account_number'])
        bank_name = data.get('bank_name', method['bank_name'])
        is_active = data.get('is_active', method['is_active'])
        display_order = data.get('display_order', method['display_order'])
        
        cur.execute("""
            UPDATE payment_methods 
            SET method_name = %s, description = %s, account_number = %s, 
                bank_name = %s, is_active = %s, display_order = %s
            WHERE id = %s
        """, (method_name, description, account_number, bank_name, is_active, 
              display_order, method_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Payment method updated'})
    except Exception as e:
        print(f"Error updating payment method: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/payment-methods/<int:method_id>/set-balance', methods=['POST'])
@perm('finance_master.edit')
def set_payment_method_balance(method_id):
    """Set/adjust current balance for a payment method"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        new_balance = float(data.get('balance', 0))
        reason = data.get('reason', 'Manual balance adjustment')
        
        conn, cur = connection()
        
        cur.execute("SELECT current_balance FROM payment_methods WHERE id = %s", (method_id,))
        method = cur.fetchone()
        if not method:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Payment method not found'}), 404
        
        old_balance = float(method['current_balance'] or 0)
        change_amount = new_balance - old_balance
        
        # Update balance
        cur.execute("""
            UPDATE payment_methods SET current_balance = %s WHERE id = %s
        """, (new_balance, method_id))
        
        # Record in history
        cur.execute("""
            INSERT INTO payment_method_balance_history
            (payment_method_id, previous_balance, change_amount, new_balance, 
             change_type, description, created_by)
            VALUES (%s, %s, %s, %s, 'adjustment', %s, %s)
        """, (method_id, old_balance, change_amount, new_balance, reason, 
              session.get('user_name')))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Balance updated', 
                        'old_balance': old_balance, 'new_balance': new_balance})
    except Exception as e:
        print(f"Error setting balance: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/payment-methods/<int:method_id>/history', methods=['GET'])
@perm('finance_master.view')
def get_payment_method_history(method_id):
    """Get balance history for a payment method"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        cur.execute("""
            SELECT h.*, ft.transaction_code
            FROM payment_method_balance_history h
            LEFT JOIN finance_transactions ft ON h.transaction_id = ft.id
            WHERE h.payment_method_id = %s
            ORDER BY h.created_at DESC
            LIMIT 100
        """, (method_id,))
        history = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'history': [{
                'id': h['id'],
                'previous_balance': float(h['previous_balance']),
                'change_amount': float(h['change_amount']),
                'new_balance': float(h['new_balance']),
                'change_type': h['change_type'],
                'description': h['description'],
                'transaction_code': h['transaction_code'],
                'created_by': h['created_by'],
                'created_at': h['created_at'].isoformat() if h['created_at'] else None
            } for h in history]
        })
    except Exception as e:
        print(f"Error getting history: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ----------------------- FINANCE CATEGORIES -----------------------

@app.route('/api/finance/categories', methods=['GET'])
@perm('finance_master.view')
def get_finance_categories():
    """Get all finance categories (hierarchical)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        category_type = request.args.get('type')  # 'income' or 'expense'
        parent_only = request.args.get('parent_only', 'false').lower() == 'true'
        
        conn, cur = connection()
        
        query = """
            SELECT id, category_name, category_code, parent_id, category_type,
                   description, is_system, is_active, display_order
            FROM finance_categories
            WHERE is_active = TRUE
        """
        params = []
        
        if category_type:
            query += " AND category_type = %s"
            params.append(category_type)
        
        if parent_only:
            query += " AND parent_id IS NULL"
        
        query += " ORDER BY category_type, display_order, category_name"
        
        cur.execute(query, params)
        categories = cur.fetchall()
        cur.close()
        conn.close()
        
        # Build hierarchical structure
        cat_dict = {}
        root_cats = []
        
        for cat in categories:
            cat_data = {
                'id': cat['id'],
                'category_name': cat['category_name'],
                'category_code': cat['category_code'],
                'parent_id': cat['parent_id'],
                'category_type': cat['category_type'],
                'description': cat['description'],
                'is_system': bool(cat['is_system']),
                'is_active': bool(cat['is_active']),
                'display_order': cat['display_order'],
                'subcategories': []
            }
            cat_dict[cat['id']] = cat_data
        
        for cat in categories:
            if cat['parent_id'] and cat['parent_id'] in cat_dict:
                cat_dict[cat['parent_id']]['subcategories'].append(cat_dict[cat['id']])
            elif not cat['parent_id']:
                root_cats.append(cat_dict[cat['id']])
        
        return jsonify({'success': True, 'categories': root_cats})
    except Exception as e:
        print(f"Error getting categories: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/categories', methods=['POST'])
@perm('finance_master.edit')
def add_finance_category():
    """Add a new finance category or sub-category"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        category_name = data.get('category_name', '').strip()
        category_type = data.get('category_type')  # 'income' or 'expense'
        parent_id = data.get('parent_id')
        description = data.get('description', '')
        
        if not category_name:
            return jsonify({'success': False, 'error': 'Category name is required'}), 400
        
        conn, cur = connection()
        
        # If parent_id is provided, inherit category_type from parent
        if parent_id:
            cur.execute("SELECT category_type FROM finance_categories WHERE id = %s", (parent_id,))
            parent = cur.fetchone()
            if parent:
                category_type = parent['category_type']
            else:
                cur.close()
                conn.close()
                return jsonify({'success': False, 'error': 'Parent category not found'}), 404
        elif not category_type:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Category type is required for root categories'}), 400
        
        # Generate category code
        code_base = category_name.upper().replace(' ', '_')[:20]
        category_code = f"{code_base}_{int(datetime.now().timestamp())}"
        
        cur.execute("""
            INSERT INTO finance_categories 
            (category_name, category_code, parent_id, category_type, description, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (category_name, category_code, parent_id, category_type, description, 
              session.get('user_name')))
        
        cat_id = cur.lastrowid
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Category added', 'id': cat_id})
    except Exception as e:
        print(f"Error adding category: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/categories/<int:cat_id>', methods=['PUT'])
@perm('finance_master.edit')
def update_finance_category(cat_id):
    """Update a finance category"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        conn, cur = connection()
        
        cur.execute("SELECT * FROM finance_categories WHERE id = %s", (cat_id,))
        cat = cur.fetchone()
        if not cat:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Category not found'}), 404
        
        if cat['is_system']:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Cannot modify system categories'}), 400
        
        category_name = data.get('category_name', cat['category_name'])
        description = data.get('description', cat['description'])
        is_active = data.get('is_active', cat['is_active'])
        display_order = data.get('display_order', cat['display_order'])
        
        cur.execute("""
            UPDATE finance_categories 
            SET category_name = %s, description = %s, is_active = %s, display_order = %s
            WHERE id = %s
        """, (category_name, description, is_active, display_order, cat_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Category updated'})
    except Exception as e:
        print(f"Error updating category: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/categories/<int:cat_id>', methods=['DELETE'])
@perm('finance_master.edit')
def delete_finance_category(cat_id):
    """Soft delete a finance category and all its subcategories
    
    This performs a soft delete (is_active=0) to preserve historical data in:
    - Finance tree reports
    - Income statements
    - Balance sheets
    - Transaction history
    
    Categories with is_active=0 won't appear in dropdowns but their data
    remains intact for all reporting purposes.
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Get category details
        cur.execute("SELECT * FROM finance_categories WHERE id = %s", (cat_id,))
        cat = cur.fetchone()
        if not cat:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Category not found'}), 404
        
        if cat['is_system']:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Cannot delete system categories | لا يمكن حذف الفئات الأساسية'}), 400
        
        # Get all subcategory IDs recursively
        subcategory_ids = []
        def get_subcategories(parent_id):
            cur.execute("SELECT id FROM finance_categories WHERE parent_id = %s", (parent_id,))
            subs = cur.fetchall()
            for sub in subs:
                subcategory_ids.append(sub['id'])
                get_subcategories(sub['id'])
        
        get_subcategories(cat_id)
        
        # All category IDs to soft delete (parent + all subcategories)
        all_ids = [cat_id] + subcategory_ids
        deleted_count = len(all_ids)
        
        # Soft delete - set is_active = FALSE for all
        # This preserves the category data for historical reports
        placeholders = ','.join(['%s'] * len(all_ids))
        cur.execute(f"""
            UPDATE finance_categories 
            SET is_active = FALSE 
            WHERE id IN ({placeholders})
        """, all_ids)
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'Category and {len(subcategory_ids)} subcategories deleted | تم حذف الفئة و {len(subcategory_ids)} فئة فرعية',
            'deleted_count': deleted_count
        })
    except Exception as e:
        print(f"Error deleting category: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ----------------------- FINANCE TRANSACTIONS -----------------------

def generate_transaction_code():
    """Generate unique transaction code"""
    prefix = datetime.now().strftime('FIN%Y%m')
    random_part = ''.join([str(random.randint(0, 9)) for _ in range(5)])
    return f"{prefix}-{random_part}"


@app.route('/api/finance/transactions', methods=['GET'])
@perm('finance_txn.view')
def get_finance_transactions():
    """Get finance transactions with filters"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        # Filters
        transaction_type = request.args.get('type')  # 'income' or 'expense'
        status = request.args.get('status')
        payment_method_id = request.args.get('payment_method_id')
        payment_method_ids = request.args.get('payment_method_ids')  # comma-separated for multi-select
        category_id = request.args.get('category_id')
        category_ids = request.args.get('category_ids')  # comma-separated for multi-select
        client_id = request.args.get('client_id')
        client_ids = request.args.get('client_ids')  # comma-separated for multi-select
        supplier_id = request.args.get('supplier_id')
        supplier_ids = request.args.get('supplier_ids')  # comma-separated for multi-select
        sales_request_id = request.args.get('sales_request_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        conn, cur = connection()
        
        query = """
            SELECT ft.*, ft.serial_number,
                   pm.method_name as payment_method_name,
                   fc.category_name,
                   fsc.category_name as subcategory_name,
                   COALESCE(c.client_name, sr_client.client_name) as client_name,
                   COALESCE(ft.client_id, sr.client_id) as resolved_client_id,
                   COALESCE(s.company_name, sr_sup.company_name) as supplier_name,
                   COALESCE(ft.supplier_id, sri.supplier_id) as resolved_supplier_id,
                   sr.id as sales_request_id_ref,
                   co.company_name as company_name
            FROM finance_transactions ft
            LEFT JOIN payment_methods pm ON ft.payment_method_id = pm.id
            LEFT JOIN finance_categories fc ON ft.category_id = fc.id
            LEFT JOIN finance_categories fsc ON ft.subcategory_id = fsc.id
            LEFT JOIN client c ON ft.client_id = c.id
            LEFT JOIN supplier s ON ft.supplier_id = s.id
            LEFT JOIN sales_request sr ON ft.sales_request_id = sr.id
            LEFT JOIN company co ON sr.company_id = co.id
            LEFT JOIN client sr_client ON sr.client_id = sr_client.id AND ft.client_id IS NULL
            LEFT JOIN (
                SELECT request_id, MIN(supplier_id) as supplier_id
                FROM sales_request_items
                WHERE supplier_id IS NOT NULL
                GROUP BY request_id
            ) sri ON ft.sales_request_id = sri.request_id AND ft.supplier_id IS NULL
            LEFT JOIN supplier sr_sup ON sri.supplier_id = sr_sup.id
            WHERE 1=1
        """
        params = []
        
        if transaction_type:
            query += " AND ft.transaction_type = %s"
            params.append(transaction_type)
        if status:
            query += " AND ft.status = %s"
            params.append(status)
        # Payment method: multi-select or single
        if payment_method_ids:
            pm_list = [int(x) for x in payment_method_ids.split(',') if x.strip().isdigit()]
            if pm_list:
                placeholders = ','.join(['%s'] * len(pm_list))
                query += f" AND ft.payment_method_id IN ({placeholders})"
                params.extend(pm_list)
        elif payment_method_id:
            query += " AND ft.payment_method_id = %s"
            params.append(payment_method_id)
        # Category: multi-select or single
        if category_ids:
            cat_list = [int(x) for x in category_ids.split(',') if x.strip().isdigit()]
            if cat_list:
                placeholders = ','.join(['%s'] * len(cat_list))
                query += f" AND (ft.category_id IN ({placeholders}) OR ft.subcategory_id IN ({placeholders}))"
                params.extend(cat_list)
                params.extend(cat_list)
        elif category_id:
            query += " AND (ft.category_id = %s OR ft.subcategory_id = %s)"
            params.extend([category_id, category_id])
        # Client: multi-select or single
        if client_ids:
            cl_list = [int(x) for x in client_ids.split(',') if x.strip().isdigit()]
            if cl_list:
                placeholders = ','.join(['%s'] * len(cl_list))
                query += f" AND ft.client_id IN ({placeholders})"
                params.extend(cl_list)
        elif client_id:
            query += " AND ft.client_id = %s"
            params.append(client_id)
        # Supplier: multi-select or single
        if supplier_ids:
            sup_list = [int(x) for x in supplier_ids.split(',') if x.strip().isdigit()]
            if sup_list:
                placeholders = ','.join(['%s'] * len(sup_list))
                query += f" AND ft.supplier_id IN ({placeholders})"
                params.extend(sup_list)
        elif supplier_id:
            query += " AND ft.supplier_id = %s"
            params.append(supplier_id)
        if sales_request_id:
            query += " AND ft.sales_request_id = %s"
            params.append(sales_request_id)
        if start_date:
            query += " AND ft.transaction_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND ft.transaction_date <= %s"
            params.append(end_date)
        
        # Get total count - build clean count query with same WHERE conditions
        count_query = "SELECT COUNT(*) as total FROM finance_transactions ft WHERE 1=1"
        count_params = []
        
        if transaction_type:
            count_query += " AND ft.transaction_type = %s"
            count_params.append(transaction_type)
        if status:
            count_query += " AND ft.status = %s"
            count_params.append(status)
        if payment_method_ids:
            pm_list_c = [int(x) for x in payment_method_ids.split(',') if x.strip().isdigit()]
            if pm_list_c:
                count_query += f" AND ft.payment_method_id IN ({','.join(['%s'] * len(pm_list_c))})"
                count_params.extend(pm_list_c)
        elif payment_method_id:
            count_query += " AND ft.payment_method_id = %s"
            count_params.append(payment_method_id)
        if category_ids:
            cat_list_c = [int(x) for x in category_ids.split(',') if x.strip().isdigit()]
            if cat_list_c:
                ph = ','.join(['%s'] * len(cat_list_c))
                count_query += f" AND (ft.category_id IN ({ph}) OR ft.subcategory_id IN ({ph}))"
                count_params.extend(cat_list_c)
                count_params.extend(cat_list_c)
        elif category_id:
            count_query += " AND (ft.category_id = %s OR ft.subcategory_id = %s)"
            count_params.extend([category_id, category_id])
        if client_ids:
            cl_list_c = [int(x) for x in client_ids.split(',') if x.strip().isdigit()]
            if cl_list_c:
                count_query += f" AND ft.client_id IN ({','.join(['%s'] * len(cl_list_c))})"
                count_params.extend(cl_list_c)
        elif client_id:
            count_query += " AND ft.client_id = %s"
            count_params.append(client_id)
        if supplier_ids:
            sup_list_c = [int(x) for x in supplier_ids.split(',') if x.strip().isdigit()]
            if sup_list_c:
                count_query += f" AND ft.supplier_id IN ({','.join(['%s'] * len(sup_list_c))})"
                count_params.extend(sup_list_c)
        elif supplier_id:
            count_query += " AND ft.supplier_id = %s"
            count_params.append(supplier_id)
        if sales_request_id:
            count_query += " AND ft.sales_request_id = %s"
            count_params.append(sales_request_id)
        if start_date:
            count_query += " AND ft.transaction_date >= %s"
            count_params.append(start_date)
        if end_date:
            count_query += " AND ft.transaction_date <= %s"
            count_params.append(end_date)
        
        cur.execute(count_query, count_params)
        total = cur.fetchone()['total']
        
        query += " ORDER BY ft.transaction_date DESC, ft.id DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cur.execute(query, params)
        transactions = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'total': total,
            'transactions': [{
                'id': t['id'],
                'serial_number': t['serial_number'],
                'transaction_code': t['transaction_code'],
                'transaction_type': t['transaction_type'],
                'amount': float(t['amount']),
                'payment_method_id': t['payment_method_id'],
                'payment_method_name': t['payment_method_name'],
                'category_id': t['category_id'],
                'category_name': t['category_name'],
                'subcategory_id': t['subcategory_id'],
                'subcategory_name': t['subcategory_name'],
                'client_id': t['resolved_client_id'],
                'client_name': t['client_name'],
                'supplier_id': t['resolved_supplier_id'],
                'supplier_name': t['supplier_name'],
                'sales_request_id': t['sales_request_id'],
                'request_number': f"SR-{t['sales_request_id']}" if t['sales_request_id'] else None,
                'description': t['description'],
                'reference_number': t['reference_number'],
                'transaction_date': t['transaction_date'].isoformat() if t['transaction_date'] else None,
                'notes': t['notes'],
                'status': t['status'],
                'added_by': t['added_by'],
                'added_at': t['added_at'].isoformat() if t['added_at'] else None,
                'approved_by': t['approved_by'],
                'approved_at': t['approved_at'].isoformat() if t['approved_at'] else None,
                'approval_notes': t['approval_notes'],
                'rejected_by': t['rejected_by'],
                'rejected_at': t['rejected_at'].isoformat() if t['rejected_at'] else None,
                'rejection_reason': t['rejection_reason'],
                'balance_before': float(t['balance_before']) if t['balance_before'] else None,
                'balance_after': float(t['balance_after']) if t['balance_after'] else None,
                'company_name': t.get('company_name')
            } for t in transactions]
        })
    except Exception as e:
        print(f"Error getting transactions: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/transactions', methods=['POST'])
@perm('finance_txn.create')
def add_finance_transaction():
    """Add a new finance transaction (pending approval)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        
        transaction_type = data.get('transaction_type')  # 'income' or 'expense'
        amount = float(data.get('amount', 0))
        payment_method_id = data.get('payment_method_id')
        category_id = data.get('category_id')
        subcategory_id = data.get('subcategory_id')
        client_id = data.get('client_id')
        supplier_id = data.get('supplier_id')
        sales_request_id = data.get('sales_request_id')
        loan_user_id = data.get('loan_user_id')  # For Loan/Pay Loan transactions
        description = data.get('description', '')
        reference_number = data.get('reference_number', '')
        transaction_date = data.get('transaction_date', datetime.now().strftime('%Y-%m-%d'))
        notes = data.get('notes', '')
        
        # Check if this is a loan-related category (Loan=11, Pay Loan=3)
        is_loan_category = str(category_id) in ['11', '3']
        loan_type = 'loan' if str(category_id) == '11' else 'pay_loan' if str(category_id) == '3' else None
        
        # Validation
        if not transaction_type or transaction_type not in ['income', 'expense']:
            return jsonify({'success': False, 'error': 'Valid transaction type required'}), 400
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Amount must be positive'}), 400
        if not payment_method_id:
            return jsonify({'success': False, 'error': 'Payment method required'}), 400
        if not category_id:
            return jsonify({'success': False, 'error': 'Category required'}), 400
        
        # Validate loan user is required for loan categories
        if is_loan_category and not loan_user_id:
            return jsonify({'success': False, 'error': 'Employee selection required for Loan/Pay Loan transactions'}), 400
        
        conn, cur = connection()
        
        # Validate loan user exists if provided
        if loan_user_id:
            cur.execute("SELECT id, name FROM user WHERE id = %s", (loan_user_id,))
            loan_user = cur.fetchone()
            if not loan_user:
                cur.close()
                conn.close()
                return jsonify({'success': False, 'error': 'Selected employee not found'}), 400
        
        # Generate transaction code
        transaction_code = generate_transaction_code()
        
        # Ensure unique code
        cur.execute("SELECT id FROM finance_transactions WHERE transaction_code = %s", (transaction_code,))
        while cur.fetchone():
            transaction_code = generate_transaction_code()
            cur.execute("SELECT id FROM finance_transactions WHERE transaction_code = %s", (transaction_code,))
        
        # Check if user is admin/finance - auto-approve their transactions
        # session['roles'] is a list of role names
        user_roles = session.get('roles', [])
        is_admin_or_finance = any(role in ['admin', 'finance'] for role in user_roles)
        initial_status = 'approved' if is_admin_or_finance else 'pending'
        
        # Get the user name from session (use 'name' key which is set during login)
        user_name = session.get('name', session.get('username', 'System'))
        user_id = session.get('user_id')
        
        # Get payment method balance for approved transactions
        balance_before = None
        balance_after = None
        serial_number = None
        
        if is_admin_or_finance:
            # Generate serial number for auto-approved transactions
            cur.execute("SELECT COALESCE(MAX(serial_number), 0) + 1 as next_serial FROM finance_transactions WHERE serial_number IS NOT NULL")
            serial_number = cur.fetchone()['next_serial']
            
            cur.execute("SELECT current_balance FROM payment_methods WHERE id = %s", (payment_method_id,))
            pm_row = cur.fetchone()
            if pm_row:
                balance_before = float(pm_row['current_balance'])
                if transaction_type == 'income':
                    balance_after = balance_before + amount
                else:
                    balance_after = balance_before - amount
        
        cur.execute("""
            INSERT INTO finance_transactions
            (transaction_code, transaction_type, amount, payment_method_id, category_id,
             subcategory_id, client_id, supplier_id, sales_request_id, loan_user_id, description,
             reference_number, transaction_date, notes, status, serial_number, added_by, added_by_user_id,
             approved_by, approved_by_user_id, approved_at, balance_before, balance_after)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (transaction_code, transaction_type, amount, payment_method_id, category_id,
              subcategory_id, client_id, supplier_id, sales_request_id, loan_user_id, description,
              reference_number, transaction_date, notes, initial_status, serial_number,
              user_name, user_id,
              user_name if is_admin_or_finance else None,
              user_id if is_admin_or_finance else None,
              datetime.now() if is_admin_or_finance else None,
              balance_before, balance_after))
        
        trans_id = cur.lastrowid
        
        # Log the submission
        if is_admin_or_finance:
            # Log as auto-approved
            cur.execute("""
                INSERT INTO finance_approval_log
                (transaction_id, action, action_by, action_by_user_id, notes, previous_status, new_status)
                VALUES (%s, 'approved', %s, %s, 'Auto-approved (admin/finance user)', NULL, 'approved')
            """, (trans_id, user_name, user_id))
            
            # Update payment method balance
            if balance_after is not None:
                cur.execute("""
                    UPDATE payment_methods 
                    SET current_balance = %s, updated_at = NOW()
                    WHERE id = %s
                """, (balance_after, payment_method_id))
                
                # Log balance change
                cur.execute("""
                    INSERT INTO payment_method_balance_history
                    (payment_method_id, change_type, change_amount, previous_balance, new_balance,
                     transaction_id, description, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (payment_method_id, transaction_type, 
                      amount if transaction_type == 'income' else -amount,
                      balance_before, balance_after, trans_id,
                      f"Transaction {transaction_code}", user_name))
            
            # Handle loan tracking for auto-approved Loan/Pay Loan transactions
            if is_loan_category and loan_user_id:
                # Get current loan balance for the user
                cur.execute("""
                    SELECT total_loan_amount, total_paid_amount, current_balance
                    FROM user_loans WHERE user_id = %s
                """, (loan_user_id,))
                existing_loan = cur.fetchone()
                
                if existing_loan:
                    loan_balance_before = float(existing_loan['current_balance'])
                    if loan_type == 'loan':
                        # Adding a new loan - increase balance
                        new_total_loan = float(existing_loan['total_loan_amount']) + amount
                        new_balance = loan_balance_before + amount
                        cur.execute("""
                            UPDATE user_loans 
                            SET total_loan_amount = %s, current_balance = %s, updated_at = NOW()
                            WHERE user_id = %s
                        """, (new_total_loan, new_balance, loan_user_id))
                    else:  # pay_loan
                        # Paying back loan - decrease balance
                        new_total_paid = float(existing_loan['total_paid_amount']) + amount
                        new_balance = loan_balance_before - amount
                        cur.execute("""
                            UPDATE user_loans 
                            SET total_paid_amount = %s, current_balance = %s, updated_at = NOW()
                            WHERE user_id = %s
                        """, (new_total_paid, new_balance, loan_user_id))
                else:
                    # First loan for this user
                    loan_balance_before = 0
                    if loan_type == 'loan':
                        new_balance = amount
                        cur.execute("""
                            INSERT INTO user_loans (user_id, total_loan_amount, total_paid_amount, current_balance)
                            VALUES (%s, %s, 0, %s)
                        """, (loan_user_id, amount, amount))
                    else:  # pay_loan (shouldn't happen but handle it)
                        new_balance = -amount
                        cur.execute("""
                            INSERT INTO user_loans (user_id, total_loan_amount, total_paid_amount, current_balance)
                            VALUES (%s, 0, %s, %s)
                        """, (loan_user_id, amount, -amount))
                
                # Log the loan transaction
                cur.execute("""
                    INSERT INTO user_loan_transactions 
                    (user_id, finance_transaction_id, transaction_type, amount, 
                     balance_before, balance_after, notes, created_by, created_by_user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (loan_user_id, trans_id, loan_type, amount,
                      loan_balance_before, new_balance, notes or description, user_name, user_id))
        else:
            cur.execute("""
                INSERT INTO finance_approval_log
                (transaction_id, action, action_by, action_by_user_id, notes, previous_status, new_status)
                VALUES (%s, 'submitted', %s, %s, 'Transaction submitted for approval', NULL, 'pending')
            """, (trans_id, user_name, user_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        message = 'Transaction approved and recorded' if is_admin_or_finance else 'Transaction created and pending approval'
        return jsonify({
            'success': True, 
            'message': message,
            'id': trans_id,
            'transaction_code': transaction_code,
            'auto_approved': is_admin_or_finance
        })
    except Exception as e:
        print(f"Error adding transaction: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/transactions/<int:trans_id>', methods=['GET'])
@perm('finance_txn.view')
def get_finance_transaction(trans_id):
    """Get single transaction with full details and approval history"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        cur.execute("""
            SELECT ft.*,
                   pm.method_name as payment_method_name,
                   fc.category_name,
                   fsc.category_name as subcategory_name,
                   COALESCE(c.client_name, sr_client.client_name) as client_name,
                   COALESCE(ft.client_id, sr.client_id) as resolved_client_id,
                   COALESCE(s.company_name, sr_sup.company_name) as supplier_name,
                   COALESCE(ft.supplier_id, sri.supplier_id) as resolved_supplier_id,
                   sr.id as sales_request_id_ref,
                   co.company_name as company_name
            FROM finance_transactions ft
            LEFT JOIN payment_methods pm ON ft.payment_method_id = pm.id
            LEFT JOIN finance_categories fc ON ft.category_id = fc.id
            LEFT JOIN finance_categories fsc ON ft.subcategory_id = fsc.id
            LEFT JOIN client c ON ft.client_id = c.id
            LEFT JOIN supplier s ON ft.supplier_id = s.id
            LEFT JOIN sales_request sr ON ft.sales_request_id = sr.id
            LEFT JOIN company co ON sr.company_id = co.id
            LEFT JOIN client sr_client ON sr.client_id = sr_client.id AND ft.client_id IS NULL
            LEFT JOIN (
                SELECT request_id, MIN(supplier_id) as supplier_id
                FROM sales_request_items
                WHERE supplier_id IS NOT NULL
                GROUP BY request_id
            ) sri ON ft.sales_request_id = sri.request_id AND ft.supplier_id IS NULL
            LEFT JOIN supplier sr_sup ON sri.supplier_id = sr_sup.id
            WHERE ft.id = %s
        """, (trans_id,))
        
        t = cur.fetchone()
        if not t:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Transaction not found'}), 404
        
        # Get approval history
        cur.execute("""
            SELECT * FROM finance_approval_log
            WHERE transaction_id = %s
            ORDER BY action_at DESC
        """, (trans_id,))
        history = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'transaction': {
                'id': t['id'],
                'transaction_code': t['transaction_code'],
                'transaction_type': t['transaction_type'],
                'amount': float(t['amount']),
                'payment_method_id': t['payment_method_id'],
                'payment_method_name': t['payment_method_name'],
                'category_id': t['category_id'],
                'category_name': t['category_name'],
                'subcategory_id': t['subcategory_id'],
                'subcategory_name': t['subcategory_name'],
                'client_id': t['resolved_client_id'],
                'client_name': t['client_name'],
                'supplier_id': t['resolved_supplier_id'],
                'supplier_name': t['supplier_name'],
                'sales_request_id': t['sales_request_id'],
                'request_number': f"SR-{t['sales_request_id']}" if t['sales_request_id'] else None,
                'company_name': t.get('company_name'),
                'description': t['description'],
                'reference_number': t['reference_number'],
                'transaction_date': t['transaction_date'].isoformat() if t['transaction_date'] else None,
                'notes': t['notes'],
                'status': t['status'],
                'added_by': t['added_by'],
                'added_at': t['added_at'].isoformat() if t['added_at'] else None,
                'approved_by': t['approved_by'],
                'approved_at': t['approved_at'].isoformat() if t['approved_at'] else None,
                'approval_notes': t['approval_notes'],
                'rejected_by': t['rejected_by'],
                'rejected_at': t['rejected_at'].isoformat() if t['rejected_at'] else None,
                'rejection_reason': t['rejection_reason'],
                'balance_before': float(t['balance_before']) if t['balance_before'] else None,
                'balance_after': float(t['balance_after']) if t['balance_after'] else None
            },
            'approval_history': [{
                'id': h['id'],
                'action': h['action'],
                'action_by': h['action_by'],
                'action_at': h['action_at'].isoformat() if h['action_at'] else None,
                'notes': h['notes'],
                'previous_status': h['previous_status'],
                'new_status': h['new_status']
            } for h in history]
        })
    except Exception as e:
        print(f"Error getting transaction: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/transactions/<int:trans_id>/approve', methods=['POST'])
@perm('finance_txn.approve')
def approve_finance_transaction(trans_id):
    """Approve a pending finance transaction"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json() or {}
        approval_notes = data.get('notes', '')
        
        conn, cur = connection()
        
        # Get transaction
        cur.execute("SELECT * FROM finance_transactions WHERE id = %s", (trans_id,))
        trans = cur.fetchone()
        if not trans:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Transaction not found'}), 404
        
        if trans['status'] != 'pending':
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': f'Transaction is already {trans["status"]}'}), 400
        
        # Get current balance of payment method
        cur.execute("SELECT current_balance FROM payment_methods WHERE id = %s", 
                    (trans['payment_method_id'],))
        pm = cur.fetchone()
        current_balance = float(pm['current_balance'] or 0)
        
        # Calculate new balance
        amount = float(trans['amount'])
        if trans['transaction_type'] == 'income':
            new_balance = current_balance + amount
            change_amount = amount
        else:  # expense
            new_balance = current_balance - amount
            change_amount = -amount
        
        # Generate next serial number for approved transactions
        cur.execute("SELECT COALESCE(MAX(serial_number), 0) + 1 as next_serial FROM finance_transactions WHERE serial_number IS NOT NULL")
        next_serial = cur.fetchone()['next_serial']
        
        # Update transaction
        user_name = session.get('name', session.get('username', 'System'))
        cur.execute("""
            UPDATE finance_transactions 
            SET status = 'approved', 
                serial_number = %s,
                approved_by = %s, approved_by_user_id = %s, approved_at = NOW(),
                approval_notes = %s, balance_before = %s, balance_after = %s
            WHERE id = %s
        """, (next_serial, user_name, session.get('user_id'), approval_notes,
              current_balance, new_balance, trans_id))
        
        # Update payment method balance
        cur.execute("""
            UPDATE payment_methods SET current_balance = %s WHERE id = %s
        """, (new_balance, trans['payment_method_id']))
        
        # Record balance history
        cur.execute("""
            INSERT INTO payment_method_balance_history
            (payment_method_id, transaction_id, previous_balance, change_amount, 
             new_balance, change_type, description, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (trans['payment_method_id'], trans_id, current_balance, change_amount,
              new_balance, trans['transaction_type'], 
              f"Transaction {trans['transaction_code']} approved",
              user_name))
        
        # Log approval
        cur.execute("""
            INSERT INTO finance_approval_log
            (transaction_id, action, action_by, action_by_user_id, notes, 
             previous_status, new_status)
            VALUES (%s, 'approved', %s, %s, %s, 'pending', 'approved')
        """, (trans_id, user_name, session.get('user_id'), approval_notes))
        
        # Handle loan tracking if this is a Loan/Pay Loan transaction
        category_id = trans.get('category_id')
        loan_user_id = trans.get('loan_user_id')
        is_loan_category = str(category_id) in ['11', '3']
        loan_type = 'loan' if str(category_id) == '11' else 'pay_loan' if str(category_id) == '3' else None
        
        if is_loan_category and loan_user_id:
            # Get current loan balance for the user
            cur.execute("""
                SELECT total_loan_amount, total_paid_amount, current_balance
                FROM user_loans WHERE user_id = %s
            """, (loan_user_id,))
            existing_loan = cur.fetchone()
            
            if existing_loan:
                loan_balance_before = float(existing_loan['current_balance'])
                if loan_type == 'loan':
                    # Adding a new loan - increase balance
                    new_total_loan = float(existing_loan['total_loan_amount']) + amount
                    loan_new_balance = loan_balance_before + amount
                    cur.execute("""
                        UPDATE user_loans 
                        SET total_loan_amount = %s, current_balance = %s, updated_at = NOW()
                        WHERE user_id = %s
                    """, (new_total_loan, loan_new_balance, loan_user_id))
                else:  # pay_loan
                    # Paying back loan - decrease balance
                    new_total_paid = float(existing_loan['total_paid_amount']) + amount
                    loan_new_balance = loan_balance_before - amount
                    cur.execute("""
                        UPDATE user_loans 
                        SET total_paid_amount = %s, current_balance = %s, updated_at = NOW()
                        WHERE user_id = %s
                    """, (new_total_paid, loan_new_balance, loan_user_id))
            else:
                # First loan for this user
                loan_balance_before = 0
                if loan_type == 'loan':
                    loan_new_balance = amount
                    cur.execute("""
                        INSERT INTO user_loans (user_id, total_loan_amount, total_paid_amount, current_balance)
                        VALUES (%s, %s, 0, %s)
                    """, (loan_user_id, amount, amount))
                else:  # pay_loan
                    loan_new_balance = -amount
                    cur.execute("""
                        INSERT INTO user_loans (user_id, total_loan_amount, total_paid_amount, current_balance)
                        VALUES (%s, 0, %s, %s)
                    """, (loan_user_id, amount, -amount))
            
            # Log the loan transaction
            cur.execute("""
                INSERT INTO user_loan_transactions 
                (user_id, finance_transaction_id, transaction_type, amount, 
                 balance_before, balance_after, notes, created_by, created_by_user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (loan_user_id, trans_id, loan_type, amount,
                  loan_balance_before, loan_new_balance, trans.get('notes') or trans.get('description') or 'Approved transaction', user_name, session.get('user_id')))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': 'Transaction approved',
            'balance_before': current_balance,
            'balance_after': new_balance
        })
    except Exception as e:
        print(f"Error approving transaction: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/transactions/<int:trans_id>/reject', methods=['POST'])
@perm('finance_txn.approve')
def reject_finance_transaction(trans_id):
    """Reject a pending finance transaction"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json() or {}
        rejection_reason = data.get('reason', '')
        
        if not rejection_reason:
            return jsonify({'success': False, 'error': 'Rejection reason is required'}), 400
        
        conn, cur = connection()
        
        cur.execute("SELECT status FROM finance_transactions WHERE id = %s", (trans_id,))
        trans = cur.fetchone()
        if not trans:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Transaction not found'}), 404
        
        if trans['status'] != 'pending':
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': f'Transaction is already {trans["status"]}'}), 400
        
        user_name = session.get('name', session.get('username', 'System'))
        cur.execute("""
            UPDATE finance_transactions 
            SET status = 'rejected', 
                rejected_by = %s, rejected_by_user_id = %s, rejected_at = NOW(),
                rejection_reason = %s
            WHERE id = %s
        """, (user_name, session.get('user_id'), rejection_reason, trans_id))
        
        # Log rejection
        cur.execute("""
            INSERT INTO finance_approval_log
            (transaction_id, action, action_by, action_by_user_id, notes, 
             previous_status, new_status)
            VALUES (%s, 'rejected', %s, %s, %s, 'pending', 'rejected')
        """, (trans_id, user_name, session.get('user_id'), rejection_reason))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Transaction rejected'})
    except Exception as e:
        print(f"Error rejecting transaction: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ----------------------- FINANCE STATISTICS & DASHBOARD -----------------------

@app.route('/api/finance/statistics', methods=['GET'])
@perm('finance_txn.view')
def get_finance_statistics():
    """Get finance overview statistics"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        from datetime import datetime
        
        conn, cur = connection()
        
        # Calculate this month's date range (same logic as income statement)
        today = datetime.now().date()
        month_start = today.replace(day=1)
        month_end = today
        
        # Total balances by payment method (this is the actual cash on hand)
        cur.execute("""
            SELECT id, method_name, method_code, current_balance
            FROM payment_methods WHERE is_active = TRUE
            ORDER BY display_order
        """)
        payment_methods = cur.fetchall()
        
        total_balance = sum(float(pm['current_balance'] or 0) for pm in payment_methods)
        
        # Total Income (all time) - calculated independently from approved income transactions
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM finance_transactions 
            WHERE status = 'approved' AND transaction_type = 'income'
        """)
        total_income = float(cur.fetchone()['total'] or 0)
        
        # Total Expense (all time) - calculated independently from approved expense transactions
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM finance_transactions 
            WHERE status = 'approved' AND transaction_type = 'expense'
        """)
        total_expense = float(cur.fetchone()['total'] or 0)
        
        # Pending transactions count
        cur.execute("SELECT COUNT(*) as cnt FROM finance_transactions WHERE status = 'pending'")
        pending_count = cur.fetchone()['cnt']
        
        # This month's INCOME - using date range same as income statement
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM finance_transactions 
            WHERE status = 'approved' 
            AND transaction_type = 'income'
            AND DATE(transaction_date) BETWEEN %s AND %s
        """, (month_start, month_end))
        month_income = float(cur.fetchone()['total'] or 0)
        
        # This month's EXPENSE - using date range same as income statement
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM finance_transactions 
            WHERE status = 'approved' 
            AND transaction_type = 'expense'
            AND DATE(transaction_date) BETWEEN %s AND %s
        """, (month_start, month_end))
        month_expense = float(cur.fetchone()['total'] or 0)
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'total_balance': total_balance,
            'payment_methods': [{
                'id': pm['id'],
                'name': pm['method_name'],
                'code': pm['method_code'],
                'balance': float(pm['current_balance'] or 0)
            } for pm in payment_methods],
            'total_income': total_income,
            'total_expense': total_expense,
            'net_balance': total_income - total_expense,
            'pending_transactions': pending_count,
            'this_month': {
                'income': month_income,
                'expense': month_expense,
                'net': month_income - month_expense
            }
        })
    except Exception as e:
        print(f"Error getting finance statistics: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/tree', methods=['GET'])
@perm('finance_txn.view')
def get_finance_tree():
    """Get finance tree - categories with transaction totals"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        conn, cur = connection()
        
        # Get all categories with transaction totals
        query = """
            SELECT fc.id, fc.category_name, fc.parent_id, fc.category_type,
                   COALESCE(SUM(CASE WHEN ft.status = 'approved' THEN ft.amount ELSE 0 END), 0) as total_amount,
                   COUNT(CASE WHEN ft.status = 'approved' THEN 1 END) as transaction_count
            FROM finance_categories fc
            LEFT JOIN finance_transactions ft ON (
                (fc.id = ft.subcategory_id) OR
                (fc.id = ft.category_id AND (ft.subcategory_id IS NULL OR ft.subcategory_id = 0))
            )
        """
        
        params = []
        if start_date or end_date:
            query += " AND ft.transaction_date BETWEEN %s AND %s"
            params.extend([start_date or '1900-01-01', end_date or '2100-12-31'])
        
        query += """
            WHERE fc.is_active = TRUE
            GROUP BY fc.id, fc.category_name, fc.parent_id, fc.category_type
            ORDER BY fc.category_type, fc.display_order, fc.category_name
        """
        
        cur.execute(query, params)
        categories = cur.fetchall()
        
        # Get client breakdowns for Client Payments category (id=1)
        # Resolve client from Sales Request when ft.client_id is NULL
        client_query = """
            SELECT c.id, c.client_name,
                   COALESCE(SUM(ft.amount), 0) as total_amount,
                   COUNT(*) as transaction_count
            FROM finance_transactions ft
            LEFT JOIN sales_request sr ON ft.sales_request_id = sr.id
            INNER JOIN client c ON c.id = COALESCE(ft.client_id, sr.client_id)
            WHERE ft.status = 'approved'
              AND ft.category_id = 1
        """
        client_params = []
        if start_date or end_date:
            client_query += " AND ft.transaction_date BETWEEN %s AND %s"
            client_params.extend([start_date or '1900-01-01', end_date or '2100-12-31'])
        client_query += " GROUP BY c.id, c.client_name HAVING transaction_count > 0 ORDER BY total_amount DESC"
        cur.execute(client_query, client_params)
        client_breakdowns = [{'id': r['id'], 'name': r['client_name'], 'total': float(r['total_amount']), 'count': r['transaction_count'], 'entity_type': 'client'} for r in cur.fetchall()]
        
        # Get supplier breakdowns for Supplier Payments category (id=10)
        # Resolve supplier from ft.supplier_id, filtered to category 10 only
        supplier_query = """
            SELECT s.id, s.company_name,
                   COALESCE(SUM(ft.amount), 0) as total_amount,
                   COUNT(*) as transaction_count
            FROM finance_transactions ft
            INNER JOIN supplier s ON s.id = ft.supplier_id
            WHERE ft.status = 'approved'
              AND ft.category_id = 10
        """
        supplier_params = []
        if start_date or end_date:
            supplier_query += " AND ft.transaction_date BETWEEN %s AND %s"
            supplier_params.extend([start_date or '1900-01-01', end_date or '2100-12-31'])
        supplier_query += " GROUP BY s.id, s.company_name HAVING transaction_count > 0 ORDER BY total_amount DESC"
        cur.execute(supplier_query, supplier_params)
        supplier_breakdowns = [{'id': r['id'], 'name': r['company_name'], 'total': float(r['total_amount']), 'count': r['transaction_count'], 'entity_type': 'supplier'} for r in cur.fetchall()]
        
        cur.close()
        conn.close()
        
        # Build tree structure
        income_tree = []
        expense_tree = []
        cat_dict = {}
        
        for cat in categories:
            cat_data = {
                'id': cat['id'],
                'name': cat['category_name'],
                'type': cat['category_type'],
                'total': float(cat['total_amount']),
                'count': cat['transaction_count'],
                'children': []
            }
            cat_dict[cat['id']] = cat_data
        
        for cat in categories:
            if cat['parent_id'] and cat['parent_id'] in cat_dict:
                cat_dict[cat['parent_id']]['children'].append(cat_dict[cat['id']])
                cat_dict[cat['parent_id']]['total'] += cat_dict[cat['id']]['total']
            elif not cat['parent_id']:
                if cat['category_type'] == 'income':
                    income_tree.append(cat_dict[cat['id']])
                else:
                    expense_tree.append(cat_dict[cat['id']])
        
        # Attach client breakdowns to Client Payments category (id=1)
        if 1 in cat_dict:
            cat_dict[1]['entities'] = client_breakdowns
        
        # Attach supplier breakdowns to Supplier Payments category (id=10)
        if 10 in cat_dict:
            cat_dict[10]['entities'] = supplier_breakdowns
        
        total_income = sum(c['total'] for c in income_tree)
        total_expense = sum(c['total'] for c in expense_tree)
        
        return jsonify({
            'success': True,
            'income': {
                'total': total_income,
                'categories': income_tree
            },
            'expense': {
                'total': total_expense,
                'categories': expense_tree
            },
            'net': total_income - total_expense
        })
    except Exception as e:
        print(f"Error getting finance tree: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ----------------------- HELPER: Get Clients and Suppliers for Dropdowns -----------------------

@app.route('/api/finance/clients', methods=['GET'])
@perm('finance_report.view')
def get_finance_clients():
    """Get clients for finance dropdowns"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        cur.execute("SELECT id, client_name, email_address, mobile_number FROM client ORDER BY client_name")
        clients = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'clients': [{'id': c['id'], 'name': c['client_name'], 
                         'email': c['email_address'], 'phone': c['mobile_number']} for c in clients]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/suppliers', methods=['GET'])
@perm('finance_report.view')
def get_finance_suppliers():
    """Get suppliers for finance dropdowns"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        cur.execute("SELECT id, company_name, contact_person_name, primary_phone FROM supplier ORDER BY company_name")
        suppliers = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'suppliers': [{'id': s['id'], 'company_name': s['company_name'], 
                           'contact_person': s['contact_person_name'], 
                           'phone': s['primary_phone']} for s in suppliers]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/clients/summary', methods=['GET'])
@perm('finance_report.view')
def get_finance_clients_summary():
    """Get clients with their transaction summary under Client Payments"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        conn, cur = connection()
        
        query = """
            SELECT c.id, c.client_name, c.email_address, c.mobile_number,
                   COALESCE(SUM(CASE WHEN ft.transaction_type = 'income' AND ft.status = 'approved' THEN ft.amount ELSE 0 END), 0) as total_income,
                   COALESCE(SUM(CASE WHEN ft.transaction_type = 'expense' AND ft.status = 'approved' THEN ft.amount ELSE 0 END), 0) as total_expense,
                   COUNT(CASE WHEN ft.status = 'approved' THEN 1 END) as transaction_count
            FROM finance_transactions ft
            LEFT JOIN sales_request sr ON ft.sales_request_id = sr.id
            INNER JOIN client c ON c.id = COALESCE(ft.client_id, sr.client_id)
            WHERE ft.category_id = 1
        """
        params = []
        if start_date:
            query += " AND ft.transaction_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND ft.transaction_date <= %s"
            params.append(end_date)
        
        query += " GROUP BY c.id, c.client_name, c.email_address, c.mobile_number ORDER BY c.client_name"
        
        cur.execute(query, params)
        clients = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'clients': [{
                'id': c['id'],
                'name': c['client_name'],
                'email': c['email_address'],
                'phone': c['mobile_number'],
                'total_income': float(c['total_income']),
                'total_expense': float(c['total_expense']),
                'balance': float(c['total_income']) - float(c['total_expense']),
                'transaction_count': c['transaction_count']
            } for c in clients]
        })
    except Exception as e:
        print(f"Error getting clients summary: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/suppliers/summary', methods=['GET'])
@perm('finance_report.view')
def get_finance_suppliers_summary():
    """Get suppliers with their transaction summary under Supplier Payments"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        conn, cur = connection()
        
        query = """
            SELECT s.id, s.company_name, s.contact_person_name, s.primary_phone,
                   COALESCE(SUM(CASE WHEN ft.transaction_type = 'income' AND ft.status = 'approved' THEN ft.amount ELSE 0 END), 0) as total_income,
                   COALESCE(SUM(CASE WHEN ft.transaction_type = 'expense' AND ft.status = 'approved' THEN ft.amount ELSE 0 END), 0) as total_expense,
                   COUNT(CASE WHEN ft.status = 'approved' THEN 1 END) as transaction_count
            FROM finance_transactions ft
            INNER JOIN supplier s ON s.id = ft.supplier_id
            WHERE ft.category_id = 10
        """
        params = []
        if start_date:
            query += " AND ft.transaction_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND ft.transaction_date <= %s"
            params.append(end_date)
        
        query += " GROUP BY s.id, s.company_name, s.contact_person_name, s.primary_phone ORDER BY s.company_name"
        
        cur.execute(query, params)
        suppliers = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'suppliers': [{
                'id': s['id'],
                'company_name': s['company_name'],
                'contact_person': s['contact_person_name'],
                'phone': s['primary_phone'],
                'total_income': float(s['total_income']),
                'total_expense': float(s['total_expense']),
                'balance': float(s['total_income']) - float(s['total_expense']),
                'transaction_count': s['transaction_count']
            } for s in suppliers]
        })
    except Exception as e:
        print(f"Error getting suppliers summary: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/clients/<int:client_id>/transactions', methods=['GET'])
@perm('finance_report.view')
def get_client_transactions(client_id):
    """Get all transactions for a specific client"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Get client info
        cur.execute("SELECT id, client_name, email_address, mobile_number FROM client WHERE id = %s", (client_id,))
        client = cur.fetchone()
        if not client:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Client not found'}), 404
        
        # Get transactions - include those where client is resolved from SR
        # Also resolve supplier from SR items if ft.supplier_id is NULL
        cur.execute("""
            SELECT ft.*, pm.method_name as payment_method_name,
                   fc.category_name, fsc.category_name as subcategory_name,
                   COALESCE(s.company_name, sr_sup.company_name) as supplier_name,
                   sr.id as sr_id, co.company_name as company_name
            FROM finance_transactions ft
            LEFT JOIN payment_methods pm ON ft.payment_method_id = pm.id
            LEFT JOIN finance_categories fc ON ft.category_id = fc.id
            LEFT JOIN finance_categories fsc ON ft.subcategory_id = fsc.id
            LEFT JOIN supplier s ON ft.supplier_id = s.id
            LEFT JOIN sales_request sr ON ft.sales_request_id = sr.id
            LEFT JOIN company co ON sr.company_id = co.id
            LEFT JOIN (
                SELECT request_id, MIN(supplier_id) as supplier_id
                FROM sales_request_items
                WHERE supplier_id IS NOT NULL
                GROUP BY request_id
            ) sri ON ft.sales_request_id = sri.request_id AND ft.supplier_id IS NULL
            LEFT JOIN supplier sr_sup ON sri.supplier_id = sr_sup.id
            WHERE COALESCE(ft.client_id, sr.client_id) = %s 
              AND ft.status = 'approved'
              AND ft.category_id = 1
            ORDER BY ft.transaction_date DESC, ft.id DESC
        """, (client_id,))
        transactions = cur.fetchall()
        
        # Calculate totals
        total_income = sum(float(t['amount']) for t in transactions if t['transaction_type'] == 'income')
        total_expense = sum(float(t['amount']) for t in transactions if t['transaction_type'] == 'expense')
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'client': {
                'id': client['id'],
                'name': client['client_name'],
                'email': client['email_address'],
                'phone': client['mobile_number']
            },
            'total_income': total_income,
            'total_expense': total_expense,
            'balance': total_income - total_expense,
            'transactions': [{
                'id': t['id'],
                'transaction_code': t['transaction_code'],
                'transaction_type': t['transaction_type'],
                'amount': float(t['amount']),
                'transaction_date': t['transaction_date'].isoformat() if t['transaction_date'] else None,
                'category_name': t['category_name'],
                'subcategory_name': t.get('subcategory_name'),
                'description': t['description'],
                'payment_method_name': t['payment_method_name'],
                'supplier_name': t.get('supplier_name'),
                'company_name': t.get('company_name'),
                'request_number': f"SR-{t['sr_id']}" if t.get('sr_id') else None,
                'serial_number': t.get('serial_number')
            } for t in transactions]
        })
    except Exception as e:
        print(f"Error getting client transactions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/suppliers/<int:supplier_id>/transactions', methods=['GET'])
@perm('finance_report.view')
def get_supplier_transactions(supplier_id):
    """Get all transactions for a specific supplier"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        conn, cur = connection()
        
        # Get supplier info
        cur.execute("SELECT id, company_name, contact_person_name, primary_phone FROM supplier WHERE id = %s", (supplier_id,))
        supplier = cur.fetchone()
        if not supplier:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Supplier not found'}), 404
        
        # Get transactions - only under Supplier Payments category
        # Also resolve client from SR if ft.client_id is NULL
        cur.execute("""
            SELECT ft.*, pm.method_name as payment_method_name,
                   fc.category_name, fsc.category_name as subcategory_name,
                   COALESCE(c.client_name, sr_client.client_name) as client_name,
                   sr.id as sr_id, co.company_name as company_name
            FROM finance_transactions ft
            LEFT JOIN payment_methods pm ON ft.payment_method_id = pm.id
            LEFT JOIN finance_categories fc ON ft.category_id = fc.id
            LEFT JOIN finance_categories fsc ON ft.subcategory_id = fsc.id
            LEFT JOIN client c ON ft.client_id = c.id
            LEFT JOIN sales_request sr ON ft.sales_request_id = sr.id
            LEFT JOIN company co ON sr.company_id = co.id
            LEFT JOIN client sr_client ON sr.client_id = sr_client.id AND ft.client_id IS NULL
            WHERE ft.supplier_id = %s 
              AND ft.status = 'approved'
              AND ft.category_id = 10
            ORDER BY ft.transaction_date DESC, ft.id DESC
        """, (supplier_id,))
        transactions = cur.fetchall()
        
        # Calculate totals
        total_income = sum(float(t['amount']) for t in transactions if t['transaction_type'] == 'income')
        total_expense = sum(float(t['amount']) for t in transactions if t['transaction_type'] == 'expense')
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'supplier': {
                'id': supplier['id'],
                'company_name': supplier['company_name'],
                'contact_person': supplier['contact_person_name'],
                'phone': supplier['primary_phone']
            },
            'total_income': total_income,
            'total_expense': total_expense,
            'balance': total_income - total_expense,
            'transactions': [{
                'id': t['id'],
                'transaction_code': t['transaction_code'],
                'transaction_type': t['transaction_type'],
                'amount': float(t['amount']),
                'transaction_date': t['transaction_date'].isoformat() if t['transaction_date'] else None,
                'category_name': t['category_name'],
                'subcategory_name': t.get('subcategory_name'),
                'description': t['description'],
                'payment_method_name': t['payment_method_name'],
                'client_name': t.get('client_name'),
                'company_name': t.get('company_name'),
                'request_number': f"SR-{t['sr_id']}" if t.get('sr_id') else None,
                'serial_number': t.get('serial_number')
            } for t in transactions]
        })
    except Exception as e:
        print(f"Error getting supplier transactions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ----------------------- REPORTING API ENDPOINTS -----------------------

@app.route('/api/finance/reports/clients', methods=['GET'])
@perm('finance_report.view')
def get_finance_report_clients():
    """Get all clients with their full transaction summary (not category-filtered)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        offset = (page - 1) * per_page
        
        conn, cur = connection()
        
        where_clause = " WHERE ft.status = 'approved'"
        params = []
        if start_date:
            where_clause += " AND ft.transaction_date >= %s"
            params.append(start_date)
        if end_date:
            where_clause += " AND ft.transaction_date <= %s"
            params.append(end_date)
        
        # Count total distinct clients with transactions
        count_query = """
            SELECT COUNT(DISTINCT COALESCE(ft.client_id, sr.client_id)) as total
            FROM finance_transactions ft
            LEFT JOIN sales_request sr ON ft.sales_request_id = sr.id
        """ + where_clause + " AND COALESCE(ft.client_id, sr.client_id) IS NOT NULL"
        cur.execute(count_query, params)
        total = cur.fetchone()['total']
        
        query = """
            SELECT c.id, c.client_name, c.email_address, c.mobile_number,
                   COALESCE(SUM(CASE WHEN ft.transaction_type = 'income' AND ft.status = 'approved' THEN ft.amount ELSE 0 END), 0) as total_income,
                   COALESCE(SUM(CASE WHEN ft.transaction_type = 'expense' AND ft.status = 'approved' THEN ft.amount ELSE 0 END), 0) as total_expense,
                   COUNT(CASE WHEN ft.status = 'approved' THEN 1 END) as transaction_count
            FROM finance_transactions ft
            LEFT JOIN sales_request sr ON ft.sales_request_id = sr.id
            INNER JOIN client c ON c.id = COALESCE(ft.client_id, sr.client_id)
        """ + where_clause + """
            GROUP BY c.id, c.client_name, c.email_address, c.mobile_number
            HAVING transaction_count > 0
            ORDER BY total_income DESC
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        
        cur.execute(query, params)
        clients = cur.fetchall()
        cur.close()
        conn.close()
        
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        
        return jsonify({
            'success': True,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'clients': [{
                'id': c['id'],
                'name': c['client_name'],
                'email': c['email_address'],
                'phone': c['mobile_number'],
                'total_income': float(c['total_income']),
                'total_expense': float(c['total_expense']),
                'transaction_count': c['transaction_count']
            } for c in clients]
        })
    except Exception as e:
        print(f"Error getting client report: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/reports/suppliers', methods=['GET'])
@perm('finance_report.view')
def get_finance_report_suppliers():
    """Get all suppliers with their full transaction summary (not category-filtered)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        offset = (page - 1) * per_page
        
        conn, cur = connection()
        
        where_clause = " WHERE ft.status = 'approved'"
        params = []
        if start_date:
            where_clause += " AND ft.transaction_date >= %s"
            params.append(start_date)
        if end_date:
            where_clause += " AND ft.transaction_date <= %s"
            params.append(end_date)
        
        # Count total distinct suppliers
        count_query = """
            SELECT COUNT(DISTINCT ft.supplier_id) as total
            FROM finance_transactions ft
        """ + where_clause + " AND ft.supplier_id IS NOT NULL"
        cur.execute(count_query, params)
        total = cur.fetchone()['total']
        
        query = """
            SELECT s.id, s.company_name, s.contact_person_name, s.primary_phone,
                   COALESCE(SUM(CASE WHEN ft.transaction_type = 'income' AND ft.status = 'approved' THEN ft.amount ELSE 0 END), 0) as total_income,
                   COALESCE(SUM(CASE WHEN ft.transaction_type = 'expense' AND ft.status = 'approved' THEN ft.amount ELSE 0 END), 0) as total_expense,
                   COUNT(CASE WHEN ft.status = 'approved' THEN 1 END) as transaction_count
            FROM finance_transactions ft
            INNER JOIN supplier s ON s.id = ft.supplier_id
        """ + where_clause + """
            GROUP BY s.id, s.company_name, s.contact_person_name, s.primary_phone
            HAVING transaction_count > 0
            ORDER BY total_expense DESC
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        
        cur.execute(query, params)
        suppliers = cur.fetchall()
        cur.close()
        conn.close()
        
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        
        return jsonify({
            'success': True,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'suppliers': [{
                'id': s['id'],
                'company_name': s['company_name'],
                'contact_person': s['contact_person_name'],
                'phone': s['primary_phone'],
                'total_income': float(s['total_income']),
                'total_expense': float(s['total_expense']),
                'transaction_count': s['transaction_count']
            } for s in suppliers]
        })
    except Exception as e:
        print(f"Error getting supplier report: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/reports/payment-methods', methods=['GET'])
@perm('finance_report.view')
def get_finance_report_payment_methods():
    """Get all payment methods with transaction summaries"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        offset = (page - 1) * per_page
        
        conn, cur = connection()
        
        date_conditions = ""
        params = []
        if start_date:
            date_conditions += " AND ft.transaction_date >= %s"
            params.append(start_date)
        if end_date:
            date_conditions += " AND ft.transaction_date <= %s"
            params.append(end_date)
        
        # Count total active payment methods
        cur.execute("SELECT COUNT(*) as total FROM payment_methods WHERE is_active = 1")
        total = cur.fetchone()['total']
        
        query = """
            SELECT pm.id, pm.method_name, pm.current_balance, pm.opening_balance,
                   COALESCE(SUM(CASE WHEN ft.transaction_type = 'income' AND ft.status = 'approved' THEN ft.amount ELSE 0 END), 0) as total_income,
                   COALESCE(SUM(CASE WHEN ft.transaction_type = 'expense' AND ft.status = 'approved' THEN ft.amount ELSE 0 END), 0) as total_expense,
                   COUNT(CASE WHEN ft.status = 'approved' THEN 1 END) as transaction_count
            FROM payment_methods pm
            LEFT JOIN finance_transactions ft ON ft.payment_method_id = pm.id {date_conditions}
            WHERE pm.is_active = 1
            GROUP BY pm.id, pm.method_name, pm.current_balance, pm.opening_balance
            ORDER BY pm.method_name
            LIMIT %s OFFSET %s
        """.format(date_conditions=date_conditions)
        params.extend([per_page, offset])
        
        cur.execute(query, params)
        methods = cur.fetchall()
        cur.close()
        conn.close()
        
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        
        return jsonify({
            'success': True,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'payment_methods': [{
                'id': m['id'],
                'method_name': m['method_name'],
                'current_balance': float(m['current_balance']),
                'opening_balance': float(m['opening_balance'] or 0),
                'total_income': float(m['total_income']),
                'total_expense': float(m['total_expense']),
                'transaction_count': m['transaction_count']
            } for m in methods]
        })
    except Exception as e:
        print(f"Error getting payment method report: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/reports/clients/<int:client_id>/transactions', methods=['GET'])
@perm('finance_report.view')
def get_report_client_transactions(client_id):
    """Get all transactions for a client (for reporting - not category-filtered)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        offset = (page - 1) * per_page
        
        conn, cur = connection()
        
        where_clause = """
            WHERE COALESCE(ft.client_id, sr.client_id) = %s
              AND ft.status = 'approved'
        """
        params = [client_id]
        if start_date:
            where_clause += " AND ft.transaction_date >= %s"
            params.append(start_date)
        if end_date:
            where_clause += " AND ft.transaction_date <= %s"
            params.append(end_date)
        
        # Count total
        count_query = """
            SELECT COUNT(*) as total
            FROM finance_transactions ft
            LEFT JOIN sales_request sr ON ft.sales_request_id = sr.id
        """ + where_clause
        cur.execute(count_query, params)
        total = cur.fetchone()['total']
        
        query = """
            SELECT ft.id, ft.serial_number, ft.transaction_code, ft.transaction_type, ft.amount,
                   ft.transaction_date, ft.description, ft.status,
                   pm.method_name as payment_method_name,
                   fc.category_name, fsc.category_name as subcategory_name,
                   sr.id as sr_id
            FROM finance_transactions ft
            LEFT JOIN payment_methods pm ON ft.payment_method_id = pm.id
            LEFT JOIN finance_categories fc ON ft.category_id = fc.id
            LEFT JOIN finance_categories fsc ON ft.subcategory_id = fsc.id
            LEFT JOIN sales_request sr ON ft.sales_request_id = sr.id
        """ + where_clause + """
            ORDER BY ft.transaction_date DESC, ft.id DESC
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        
        cur.execute(query, params)
        transactions = cur.fetchall()
        cur.close()
        conn.close()
        
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        
        return jsonify({
            'success': True,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'transactions': [{
                'id': t['id'],
                'serial_number': t['serial_number'],
                'transaction_code': t['transaction_code'],
                'transaction_type': t['transaction_type'],
                'amount': float(t['amount']),
                'transaction_date': t['transaction_date'].isoformat() if t['transaction_date'] else None,
                'description': t['description'],
                'payment_method_name': t['payment_method_name'],
                'category_name': t['category_name'],
                'subcategory_name': t.get('subcategory_name'),
                'request_number': f"SR-{t['sr_id']}" if t.get('sr_id') else None
            } for t in transactions]
        })
    except Exception as e:
        print(f"Error getting client report transactions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/reports/suppliers/<int:supplier_id>/transactions', methods=['GET'])
@perm('finance_report.view')
def get_report_supplier_transactions(supplier_id):
    """Get all transactions for a supplier (for reporting - not category-filtered)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        offset = (page - 1) * per_page
        
        conn, cur = connection()
        
        where_clause = """
            WHERE ft.supplier_id = %s
              AND ft.status = 'approved'
        """
        params = [supplier_id]
        if start_date:
            where_clause += " AND ft.transaction_date >= %s"
            params.append(start_date)
        if end_date:
            where_clause += " AND ft.transaction_date <= %s"
            params.append(end_date)
        
        # Count total
        count_query = "SELECT COUNT(*) as total FROM finance_transactions ft " + where_clause
        cur.execute(count_query, params)
        total = cur.fetchone()['total']
        
        query = """
            SELECT ft.id, ft.serial_number, ft.transaction_code, ft.transaction_type, ft.amount,
                   ft.transaction_date, ft.description, ft.status,
                   pm.method_name as payment_method_name,
                   fc.category_name, fsc.category_name as subcategory_name,
                   sr.id as sr_id
            FROM finance_transactions ft
            LEFT JOIN payment_methods pm ON ft.payment_method_id = pm.id
            LEFT JOIN finance_categories fc ON ft.category_id = fc.id
            LEFT JOIN finance_categories fsc ON ft.subcategory_id = fsc.id
            LEFT JOIN sales_request sr ON ft.sales_request_id = sr.id
        """ + where_clause + """
            ORDER BY ft.transaction_date DESC, ft.id DESC
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        
        cur.execute(query, params)
        transactions = cur.fetchall()
        cur.close()
        conn.close()
        
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        
        return jsonify({
            'success': True,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'transactions': [{
                'id': t['id'],
                'serial_number': t['serial_number'],
                'transaction_code': t['transaction_code'],
                'transaction_type': t['transaction_type'],
                'amount': float(t['amount']),
                'transaction_date': t['transaction_date'].isoformat() if t['transaction_date'] else None,
                'description': t['description'],
                'payment_method_name': t['payment_method_name'],
                'category_name': t['category_name'],
                'subcategory_name': t.get('subcategory_name'),
                'request_number': f"SR-{t['sr_id']}" if t.get('sr_id') else None
            } for t in transactions]
        })
    except Exception as e:
        print(f"Error getting supplier report transactions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/sales-requests', methods=['GET'])
@perm('sales_request.view')
def get_finance_sales_requests():
    """Get sales requests for finance linking"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        client_id = request.args.get('client_id')
        
        conn, cur = connection()
        
        query = """
            SELECT sr.id, sr.title, c.client_name
            FROM sales_request sr
            LEFT JOIN client c ON sr.client_id = c.id
            WHERE sr.status != 'cancelled'
        """
        params = []
        
        if client_id:
            query += " AND sr.client_id = %s"
            params.append(client_id)
        
        query += " ORDER BY sr.created_at DESC LIMIT 100"
        
        cur.execute(query, params)
        requests = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'sales_requests': [{
                'id': r['id'], 
                'request_number': f"SR-{r['id']}",
                'title': r['title'],
                'client_name': r['client_name']
            } for r in requests]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/income-statement', methods=['GET'])
@perm('finance_report.view')
def get_income_statement():
    """Get income statement data"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        period = request.args.get('period', 'month')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        conn, cur = connection()
        
        # Calculate date range based on period
        from datetime import datetime, timedelta
        from dateutil.relativedelta import relativedelta
        
        today = datetime.now().date()
        
        if period == 'month':
            start = today.replace(day=1)
            end = today
        elif period == 'quarter':
            quarter_month = ((today.month - 1) // 3) * 3 + 1
            start = today.replace(month=quarter_month, day=1)
            end = today
        elif period == 'year':
            start = today.replace(month=1, day=1)
            end = today
        elif period == 'custom' and start_date and end_date:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            # All time - get from first transaction
            cur.execute("SELECT MIN(transaction_date) as min_date FROM finance_transactions WHERE status = 'approved'")
            result = cur.fetchone()
            start = result['min_date'] if result['min_date'] else today
            end = today
        
        # Get income by category
        cur.execute("""
            SELECT 
                fc.id as category_id,
                fc.category_name,
                fc.parent_id,
                COALESCE(SUM(ft.amount), 0) as total
            FROM finance_categories fc
            LEFT JOIN finance_transactions ft ON (ft.category_id = fc.id OR ft.subcategory_id = fc.id)
                AND ft.transaction_type = 'income'
                AND ft.status = 'approved'
                AND ft.transaction_date BETWEEN %s AND %s
            WHERE fc.category_type = 'income' AND fc.is_active = 1
            GROUP BY fc.id, fc.category_name, fc.parent_id
            ORDER BY fc.parent_id, fc.category_name
        """, (start, end))
        income_categories = cur.fetchall()
        
        # Get expense by category
        cur.execute("""
            SELECT 
                fc.id as category_id,
                fc.category_name,
                fc.parent_id,
                COALESCE(SUM(ft.amount), 0) as total
            FROM finance_categories fc
            LEFT JOIN finance_transactions ft ON (ft.category_id = fc.id OR ft.subcategory_id = fc.id)
                AND ft.transaction_type = 'expense'
                AND ft.status = 'approved'
                AND ft.transaction_date BETWEEN %s AND %s
            WHERE fc.category_type = 'expense' AND fc.is_active = 1
            GROUP BY fc.id, fc.category_name, fc.parent_id
            ORDER BY fc.parent_id, fc.category_name
        """, (start, end))
        expense_categories = cur.fetchall()
        
        # Organize hierarchically
        def organize_categories(categories):
            roots = []
            children_map = {}
            
            for cat in categories:
                cat_dict = {
                    'id': cat['category_id'],
                    'name': cat['category_name'],
                    'total': float(cat['total']),
                    'children': []
                }
                
                if cat['parent_id'] is None:
                    roots.append(cat_dict)
                else:
                    if cat['parent_id'] not in children_map:
                        children_map[cat['parent_id']] = []
                    children_map[cat['parent_id']].append(cat_dict)
            
            # Attach children
            for root in roots:
                if root['id'] in children_map:
                    root['children'] = children_map[root['id']]
                    # Add children totals to parent
                    for child in root['children']:
                        root['total'] += child['total']
            
            return roots
        
        income_tree = organize_categories(income_categories)
        expense_tree = organize_categories(expense_categories)
        
        total_income = sum(cat['total'] for cat in income_tree)
        total_expense = sum(cat['total'] for cat in expense_tree)
        net_income = total_income - total_expense
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'period': {
                'start': start.strftime('%Y-%m-%d'),
                'end': end.strftime('%Y-%m-%d'),
                'label': period
            },
            'income': {
                'categories': income_tree,
                'total': total_income
            },
            'expenses': {
                'categories': expense_tree,
                'total': total_expense
            },
            'net_income': net_income,
            'gross_margin': (net_income / total_income * 100) if total_income > 0 else 0
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/balance-sheet', methods=['GET'])
@perm('finance_report.view')
def get_balance_sheet():
    """Get balance sheet data with date range support"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        conn, cur = connection()
        
        from datetime import datetime
        
        # Parse dates
        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_dt = datetime.now().date()
            
        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            # Default to beginning of current year
            start_dt = datetime(end_dt.year, 1, 1).date()
        
        # ASSETS
        # Cash & Cash Equivalents (Payment Method Balances as of end_date)
        cur.execute("""
            SELECT method_name, current_balance, opening_balance
            FROM payment_methods
            WHERE is_active = 1
            ORDER BY method_name
        """)
        cash_accounts = cur.fetchall()
        total_cash = sum(float(acc['current_balance']) for acc in cash_accounts)
        total_opening_balance = sum(float(acc['opening_balance'] or 0) for acc in cash_accounts)
        
        # Accounts Receivable (pending income within date range)
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM finance_transactions
            WHERE transaction_type = 'income' 
            AND status = 'pending'
            AND transaction_date BETWEEN %s AND %s
        """, (start_dt, end_dt))
        accounts_receivable = float(cur.fetchone()['total'])
        
        # Total income in date range (approved)
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM finance_transactions
            WHERE transaction_type = 'income' 
            AND status = 'approved'
            AND transaction_date BETWEEN %s AND %s
        """, (start_dt, end_dt))
        period_income = float(cur.fetchone()['total'])
        
        # Total expenses in date range (approved)
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM finance_transactions
            WHERE transaction_type = 'expense' 
            AND status = 'approved'
            AND transaction_date BETWEEN %s AND %s
        """, (start_dt, end_dt))
        period_expense = float(cur.fetchone()['total'])
        
        # Historical totals (before start_date)
        cur.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN transaction_type = 'income' THEN amount ELSE 0 END), 0) as total_income,
                COALESCE(SUM(CASE WHEN transaction_type = 'expense' THEN amount ELSE 0 END), 0) as total_expense
            FROM finance_transactions
            WHERE status = 'approved'
            AND transaction_date < %s
        """, (start_dt,))
        historical = cur.fetchone()
        historical_retained = float(historical['total_income']) - float(historical['total_expense'])
        
        # LIABILITIES
        # Accounts Payable (pending expenses within date range)
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM finance_transactions
            WHERE transaction_type = 'expense' 
            AND status = 'pending'
            AND transaction_date BETWEEN %s AND %s
        """, (start_dt, end_dt))
        accounts_payable = float(cur.fetchone()['total'])
        
        # User balances (owed to users)
        cur.execute("""
            SELECT COALESCE(SUM(balance), 0) as total
            FROM user_finance_balances
        """)
        user_balances_owed = float(cur.fetchone()['total'])
        
        # Calculate totals
        total_current_assets = total_cash + accounts_receivable
        total_assets = total_current_assets
        
        total_current_liabilities = accounts_payable + user_balances_owed
        total_liabilities = total_current_liabilities
        
        # Equity = Opening Balance + Retained Earnings - User Obligations
        # User balances are obligations funded through recorded transactions,
        # so they reduce equity to keep the balance sheet balanced
        current_period_net = period_income - period_expense
        retained_earnings = historical_retained + current_period_net
        total_equity = total_opening_balance + retained_earnings - user_balances_owed
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'period': {
                'start_date': start_dt.strftime('%Y-%m-%d'),
                'end_date': end_dt.strftime('%Y-%m-%d')
            },
            'assets': {
                'current_assets': {
                    'cash_and_equivalents': {
                        'accounts': [{'name': acc['method_name'], 'balance': float(acc['current_balance']), 'opening': float(acc['opening_balance'] or 0)} for acc in cash_accounts],
                        'total': total_cash
                    },
                    'accounts_receivable': accounts_receivable,
                    'total': total_current_assets
                },
                'total': total_assets
            },
            'liabilities': {
                'current_liabilities': {
                    'accounts_payable': accounts_payable,
                    'user_balances_owed': user_balances_owed,
                    'total': total_current_liabilities
                },
                'total': total_liabilities
            },
            'equity': {
                'opening_balance': total_opening_balance,
                'historical_retained': historical_retained,
                'current_period_net': current_period_net,
                'retained_earnings': retained_earnings,
                'total': total_equity
            },
            'summary': {
                'period_income': period_income,
                'period_expense': period_expense,
                'period_net': current_period_net
            },
            'total_liabilities_and_equity': total_liabilities + total_equity
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/analytics', methods=['GET'])
@perm('finance_report.view')
def get_finance_analytics():
    """Get comprehensive finance analytics with date range support"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        from datetime import datetime, timedelta
        
        # Support both days-based and date-range queries
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        days = int(request.args.get('days', 30))
        
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            days = (end_date - start_date).days
        else:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
        
        conn, cur = connection()
        
        # Calculate previous period for comparison
        period_days = (end_date - start_date).days or 1
        prev_end_date = start_date - timedelta(days=1)
        prev_start_date = prev_end_date - timedelta(days=period_days)
        
        # Current period totals
        cur.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN transaction_type = 'income' THEN amount ELSE 0 END), 0) as total_income,
                COALESCE(SUM(CASE WHEN transaction_type = 'expense' THEN amount ELSE 0 END), 0) as total_expense,
                COUNT(*) as trans_count
            FROM finance_transactions
            WHERE status = 'approved'
            AND transaction_date BETWEEN %s AND %s
        """, (start_date, end_date))
        current = cur.fetchone()
        
        # Previous period totals (for comparison)
        cur.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN transaction_type = 'income' THEN amount ELSE 0 END), 0) as total_income,
                COALESCE(SUM(CASE WHEN transaction_type = 'expense' THEN amount ELSE 0 END), 0) as total_expense
            FROM finance_transactions
            WHERE status = 'approved'
            AND transaction_date BETWEEN %s AND %s
        """, (prev_start_date, prev_end_date))
        previous = cur.fetchone()
        
        current_income = float(current['total_income'])
        current_expense = float(current['total_expense'])
        current_profit = current_income - current_expense
        prev_income = float(previous['total_income'])
        prev_expense = float(previous['total_expense'])
        prev_profit = prev_income - prev_expense
        
        # Calculate changes
        def calc_change(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return round((current - previous) / previous * 100, 1)
        
        income_change = calc_change(current_income, prev_income)
        expense_change = calc_change(current_expense, prev_expense)
        profit_change = calc_change(current_profit, prev_profit)
        
        # Daily trend data
        cur.execute("""
            SELECT 
                DATE(transaction_date) as date,
                SUM(CASE WHEN transaction_type = 'income' THEN amount ELSE 0 END) as income,
                SUM(CASE WHEN transaction_type = 'expense' THEN amount ELSE 0 END) as expense
            FROM finance_transactions
            WHERE status = 'approved'
            AND transaction_date BETWEEN %s AND %s
            GROUP BY DATE(transaction_date)
            ORDER BY date
        """, (start_date, end_date))
        daily_data = cur.fetchall()
        
        # Income by category
        cur.execute("""
            SELECT 
                fc.category_name,
                COALESCE(SUM(ft.amount), 0) as total
            FROM finance_categories fc
            LEFT JOIN finance_transactions ft ON ft.category_id = fc.id
                AND ft.transaction_type = 'income'
                AND ft.status = 'approved'
                AND ft.transaction_date BETWEEN %s AND %s
            WHERE fc.category_type = 'income' AND fc.is_active = 1 AND fc.parent_id IS NULL
            GROUP BY fc.id, fc.category_name
            HAVING total > 0
            ORDER BY total DESC
            LIMIT 10
        """, (start_date, end_date))
        income_by_category = cur.fetchall()
        
        # Expense by category
        cur.execute("""
            SELECT 
                fc.category_name,
                COALESCE(SUM(ft.amount), 0) as total
            FROM finance_categories fc
            LEFT JOIN finance_transactions ft ON ft.category_id = fc.id
                AND ft.transaction_type = 'expense'
                AND ft.status = 'approved'
                AND ft.transaction_date BETWEEN %s AND %s
            WHERE fc.category_type = 'expense' AND fc.is_active = 1 AND fc.parent_id IS NULL
            GROUP BY fc.id, fc.category_name
            HAVING total > 0
            ORDER BY total DESC
            LIMIT 10
        """, (start_date, end_date))
        expense_by_category = cur.fetchall()
        
        # Monthly comparison (last 6 months) - with readable month names
        cur.execute("""
            SELECT 
                DATE_FORMAT(transaction_date, '%%b %%Y') as month,
                DATE_FORMAT(transaction_date, '%%Y-%%m') as month_sort,
                SUM(CASE WHEN transaction_type = 'income' THEN amount ELSE 0 END) as income,
                SUM(CASE WHEN transaction_type = 'expense' THEN amount ELSE 0 END) as expense
            FROM finance_transactions
            WHERE status = 'approved'
            AND transaction_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
            GROUP BY DATE_FORMAT(transaction_date, '%%Y-%%m'), DATE_FORMAT(transaction_date, '%%b %%Y')
            ORDER BY month_sort
        """)
        monthly_data = cur.fetchall()
        
        # Payment method usage - Income vs Expense per payment method
        cur.execute("""
            SELECT 
                pm.method_name,
                COALESCE(SUM(CASE WHEN ft.transaction_type = 'income' THEN ft.amount ELSE 0 END), 0) as total_income,
                COALESCE(SUM(CASE WHEN ft.transaction_type = 'expense' THEN ft.amount ELSE 0 END), 0) as total_expense,
                COUNT(CASE WHEN ft.transaction_type = 'income' THEN 1 END) as income_count,
                COUNT(CASE WHEN ft.transaction_type = 'expense' THEN 1 END) as expense_count
            FROM payment_methods pm
            LEFT JOIN finance_transactions ft ON ft.payment_method_id = pm.id
                AND ft.status = 'approved'
                AND ft.transaction_date BETWEEN %s AND %s
            WHERE pm.is_active = 1
            GROUP BY pm.id, pm.method_name
            ORDER BY pm.display_order, pm.method_name
        """, (start_date, end_date))
        payment_methods = cur.fetchall()
        
        # Top clients by revenue
        cur.execute("""
            SELECT 
                c.client_name,
                COUNT(ft.id) as trans_count,
                COALESCE(SUM(ft.amount), 0) as total_revenue
            FROM finance_transactions ft
            JOIN client c ON ft.client_id = c.id
            WHERE ft.transaction_type = 'income'
            AND ft.status = 'approved'
            AND ft.transaction_date BETWEEN %s AND %s
            GROUP BY c.id, c.client_name
            ORDER BY total_revenue DESC
            LIMIT 10
        """, (start_date, end_date))
        top_clients = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'period': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d'),
                'days': days
            },
            'kpis': {
                'total_revenue': current_income,
                'total_expenses': current_expense,
                'net_profit': current_profit,
                'profit_margin': round(current_profit / current_income * 100, 1) if current_income > 0 else 0,
                'transaction_count': current['trans_count'],
                'avg_transaction': round((current_income + current_expense) / current['trans_count'], 2) if current['trans_count'] > 0 else 0,
                'changes': {
                    'revenue': income_change,
                    'expenses': expense_change,
                    'profit': profit_change
                }
            },
            'trends': {
                'daily': [{'date': d['date'].strftime('%Y-%m-%d'), 'income': float(d['income']), 'expense': float(d['expense'])} for d in daily_data],
                'monthly': [{'month': m['month'], 'income': float(m['income']), 'expense': float(m['expense'])} for m in monthly_data]
            },
            'distributions': {
                'income_by_category': [{'name': c['category_name'], 'value': float(c['total'])} for c in income_by_category],
                'expense_by_category': [{'name': c['category_name'], 'value': float(c['total'])} for c in expense_by_category]
            },
            'payment_methods': [{
                'name': pm['method_name'], 
                'income': float(pm['total_income']), 
                'expense': float(pm['total_expense']),
                'income_count': pm['income_count'],
                'expense_count': pm['expense_count']
            } for pm in payment_methods],
            'top_clients': [{'name': c['client_name'], 'count': c['trans_count'], 'revenue': float(c['total_revenue'])} for c in top_clients]
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# FINANCE APPROVAL PAGE
# ============================================================================

@app.route('/finance/approvals')
@perm('finance_txn.approve')
def finance_approvals():
    """Finance Approvals Page"""
    return render_template('finance_approvals.html')


# ============================================================================
# USER BALANCE MANAGEMENT
# ============================================================================

@app.route('/api/finance/user-balances', methods=['GET'])
@perm('user_balance.view')
def get_user_balances():
    """Get all user balances"""
    try:
        conn, cur = connection()
        
        cur.execute("""
            SELECT 
                u.id as user_id,
                u.name as user_name,
                u.email,
                rr.name as roles,
                COALESCE(ufb.balance, 0) as balance,
                ufb.last_updated
            FROM user u
            LEFT JOIN user_finance_balances ufb ON u.id = ufb.user_id
            LEFT JOIN rbac_role rr ON rr.id = u.rbac_role_id
            GROUP BY u.id, u.name, u.email, rr.name, ufb.balance, ufb.last_updated
            ORDER BY u.name
        """)
        users = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/user-balances/<int:user_id>', methods=['GET'])
@perm('user_balance.view')
def get_user_balance(user_id):
    """Get specific user balance"""
    try:
        if not session.get('user_id'):
            return jsonify({'success': False, 'error': 'Not logged in'}), 401
        
        # Own scope sees only themselves; team and department scope reach their
        # reports; finance holds it at 'all'.
        assert_scope('user_balance.view', user_id)

        conn, cur = connection()
        
        cur.execute("""
            SELECT 
                u.id as user_id,
                u.name as user_name,
                COALESCE(ufb.balance, 0) as balance,
                ufb.last_updated
            FROM user u
            LEFT JOIN user_finance_balances ufb ON u.id = ufb.user_id
            WHERE u.id = %s
        """, (user_id,))
        user = cur.fetchone()
        
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        # Get recent history
        cur.execute("""
            SELECT 
                ubh.*,
                u.name as created_by_name
            FROM user_balance_history ubh
            LEFT JOIN user u ON ubh.created_by = u.id
            WHERE ubh.user_id = %s
            ORDER BY ubh.created_at DESC
            LIMIT 20
        """, (user_id,))
        history = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'user': user, 'history': history})
    # A scope refusal is a 403, not a server error.
    except HTTPException:
        raise
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/my-balance', methods=['GET'])
@perm('user_balance.view')
def get_my_balance():
    """Get current user's balance"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'Not logged in'}), 401
        
        conn, cur = connection()
        
        cur.execute("""
            SELECT COALESCE(balance, 0) as balance, last_updated
            FROM user_finance_balances
            WHERE user_id = %s
        """, (user_id,))
        result = cur.fetchone()
        
        balance = result['balance'] if result else 0
        
        # Get pending requests
        cur.execute("""
            SELECT COUNT(*) as pending_count
            FROM user_balance_transfers
            WHERE to_user_id = %s AND status = 'pending' AND transfer_type = 'user_request'
        """, (user_id,))
        pending = cur.fetchone()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'balance': float(balance),
            'pending_requests': pending['pending_count'] if pending else 0
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/my-balance-history', methods=['GET'])
@perm('user_balance.view')
def get_my_balance_history():
    """Get current user's balance history (internal transfers)"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'Not logged in'}), 401
        
        conn, cur = connection()
        
        cur.execute("""
            SELECT 
                ubh.id,
                ubh.change_type,
                ubh.change_amount,
                ubh.balance_before,
                ubh.balance_after,
                ubh.reference_id,
                ubh.reference_type,
                ubh.description,
                ubh.created_at,
                u.name as created_by_name
            FROM user_balance_history ubh
            LEFT JOIN user u ON ubh.created_by = u.id
            WHERE ubh.user_id = %s
            ORDER BY ubh.created_at DESC
            LIMIT 50
        """, (user_id,))
        history = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'history': history})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/transfer-balance', methods=['POST'])
@perm('user_balance.transfer')
def transfer_balance_to_user():
    """Admin transfers balance to a user from a payment method"""
    try:
        data = request.get_json()
        to_user_id = data.get('to_user_id')
        amount = float(data.get('amount', 0))
        description = data.get('description', '')
        payment_method_id = data.get('payment_method_id')
        
        if not to_user_id or amount <= 0:
            return jsonify({'success': False, 'error': 'Invalid user or amount'}), 400
        
        if not payment_method_id:
            return jsonify({'success': False, 'error': 'Payment method is required'}), 400
        
        conn, cur = connection()
        
        # Verify payment method exists and has sufficient balance
        cur.execute("""
            SELECT id, method_name, current_balance 
            FROM payment_methods 
            WHERE id = %s AND is_active = 1
        """, (payment_method_id,))
        pm = cur.fetchone()
        
        if not pm:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Invalid or inactive payment method'}), 400
        
        pm_balance = float(pm['current_balance'] or 0)
        if pm_balance < amount:
            cur.close()
            conn.close()
            return jsonify({
                'success': False, 
                'error': f"Insufficient balance in {pm['method_name']}. Available: {pm_balance:.2f}, Required: {amount:.2f}"
            }), 400
        
        # Generate transfer code
        import random
        transfer_code = f"TRF-{random.randint(10000, 99999)}"
        
        # Get current user balance
        cur.execute("SELECT COALESCE(balance, 0) as balance FROM user_finance_balances WHERE user_id = %s", (to_user_id,))
        result = cur.fetchone()
        balance_before = float(result['balance']) if result else 0
        balance_after = balance_before + amount
        
        # Deduct from payment method balance
        cur.execute("""
            UPDATE payment_methods 
            SET current_balance = current_balance - %s 
            WHERE id = %s
        """, (amount, payment_method_id))
        
        # Create or update user balance
        cur.execute("""
            INSERT INTO user_finance_balances (user_id, balance)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE balance = balance + %s, last_updated = NOW()
        """, (to_user_id, amount, amount))
        
        # Create transfer record (auto-approved for admin)
        cur.execute("""
            INSERT INTO user_balance_transfers 
            (transfer_code, from_user_id, to_user_id, amount, transfer_type, status, description, requested_by, approved_by, approved_at)
            VALUES (%s, NULL, %s, %s, 'admin_transfer', 'approved', %s, %s, %s, NOW())
        """, (transfer_code, to_user_id, amount, description, session.get('user_id'), session.get('user_id')))
        
        transfer_id = cur.lastrowid
        
        # Create history record with payment method reference
        full_description = f"{description} (from {pm['method_name']})" if description else f"Transfer from {pm['method_name']}"
        cur.execute("""
            INSERT INTO user_balance_history 
            (user_id, change_type, change_amount, balance_before, balance_after, reference_id, reference_type, description, created_by)
            VALUES (%s, 'transfer_in', %s, %s, %s, %s, 'transfer', %s, %s)
        """, (to_user_id, amount, balance_before, balance_after, transfer_id, full_description, session.get('user_id')))
        
        # Also record as a finance transaction (expense from PM for internal transfer)
        # Category 16 = 'Internal Transfer' (expense category)
        from datetime import date
        
        # Get next serial number
        cur.execute("SELECT COALESCE(MAX(serial_number), 0) + 1 as next_serial FROM finance_transactions WHERE serial_number IS NOT NULL")
        next_serial = cur.fetchone()['next_serial']
        
        # Balance was already deducted above, so balance_before = current + amount, balance_after = current
        cur.execute("SELECT current_balance FROM payment_methods WHERE id = %s", (payment_method_id,))
        pm_current = cur.fetchone()
        pm_balance_after = float(pm_current['current_balance']) if pm_current else 0
        pm_balance_before = pm_balance_after + amount  # before the deduction
        
        cur.execute("""
            INSERT INTO finance_transactions 
            (transaction_code, transaction_type, amount, payment_method_id, category_id, transaction_date, 
             description, status, serial_number, added_by, added_by_user_id,
             approved_by, approved_by_user_id, approved_at, balance_before, balance_after)
            VALUES (%s, 'expense', %s, %s, 16, %s, %s, 'approved', %s, %s, %s, %s, %s, NOW(), %s, %s)
        """, (transfer_code, amount, payment_method_id, date.today(), 
              f"User balance transfer to {full_description}", 
              next_serial, session.get('name'), session.get('user_id'),
              session.get('name'), session.get('user_id'), pm_balance_before, pm_balance_after))
        
        finance_trans_id = cur.lastrowid
        
        # Log balance change in payment method history
        cur.execute("""
            INSERT INTO payment_method_balance_history
            (payment_method_id, change_type, change_amount, previous_balance, new_balance,
             transaction_id, description, created_by)
            VALUES (%s, 'expense', %s, %s, %s, %s, %s, %s)
        """, (payment_method_id, -amount, pm_balance_before, pm_balance_after, finance_trans_id,
              f"Balance transfer {transfer_code}", session.get('name')))
        
        # Log finance approval
        cur.execute("""
            INSERT INTO finance_approval_log
            (transaction_id, action, action_by, action_by_user_id, notes, previous_status, new_status)
            VALUES (%s, 'approved', %s, %s, %s, NULL, 'approved')
        """, (finance_trans_id, session.get('name'), session.get('user_id'), f"Admin transfer {transfer_code}"))
        
        conn.commit()
        
        # Get new payment method balance
        cur.execute("SELECT current_balance FROM payment_methods WHERE id = %s", (payment_method_id,))
        new_pm = cur.fetchone()
        new_pm_balance = float(new_pm['current_balance'] or 0) if new_pm else 0
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'transfer_code': transfer_code, 
            'new_user_balance': balance_after,
            'new_pm_balance': new_pm_balance,
            'message': f"Successfully transferred {amount:.2f} to user from {pm['method_name']}"
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/request-balance', methods=['POST'])
@perm('user_balance.request')
def request_balance():
    """User requests balance from admin"""
    try:
        if not session.get('user_id'):
            return jsonify({'success': False, 'error': 'Not logged in'}), 401
        
        data = request.get_json()
        amount = float(data.get('amount', 0))
        description = data.get('description', '')
        
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Invalid amount'}), 400
        
        conn, cur = connection()
        
        # Generate transfer code
        import random
        transfer_code = f"REQ-{random.randint(10000, 99999)}"
        
        # Create pending request
        cur.execute("""
            INSERT INTO user_balance_transfers 
            (transfer_code, from_user_id, to_user_id, amount, transfer_type, status, description, requested_by)
            VALUES (%s, NULL, %s, %s, 'user_request', 'pending', %s, %s)
        """, (transfer_code, session.get('user_id'), amount, description, session.get('user_id')))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'transfer_code': transfer_code, 'message': 'Balance request submitted for approval'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/balance-requests', methods=['GET'])
@perm('user_balance.view')
def get_balance_requests():
    """Get balance requests - admin sees all pending, users see their own"""
    try:
        if not session.get('user_id'):
            return jsonify({'success': False, 'error': 'Not logged in'}), 401
        
        conn, cur = connection()
        
        # Scope decides breadth: 'all' sees every request, anything narrower
        # falls back to the caller's own transfers.
        is_admin = visible_user_ids('user_balance.view') is None
        user_id = session.get('user_id')

        if is_admin:
            # Unrestricted scope sees all
            status_filter = request.args.get('status', '')
            query = """
                SELECT 
                    ubt.*,
                    u_to.name as to_user_name,
                    u_req.name as requested_by_name,
                    u_app.name as approved_by_name
                FROM user_balance_transfers ubt
                LEFT JOIN user u_to ON ubt.to_user_id = u_to.id
                LEFT JOIN user u_req ON ubt.requested_by = u_req.id
                LEFT JOIN user u_app ON ubt.approved_by = u_app.id
                WHERE 1=1
            """
            params = []
            if status_filter:
                query += " AND ubt.status = %s"
                params.append(status_filter)
            query += " ORDER BY ubt.created_at DESC LIMIT 100"
            cur.execute(query, params)
        else:
            # User sees only their requests
            cur.execute("""
                SELECT 
                    ubt.*,
                    u_app.name as approved_by_name
                FROM user_balance_transfers ubt
                LEFT JOIN user u_app ON ubt.approved_by = u_app.id
                WHERE ubt.to_user_id = %s OR ubt.requested_by = %s
                ORDER BY ubt.created_at DESC
                LIMIT 50
            """, (user_id, user_id))
        
        requests_list = cur.fetchall()
        
        # Get pending count for admin
        pending_count = 0
        if is_admin:
            cur.execute("SELECT COUNT(*) as cnt FROM user_balance_transfers WHERE status = 'pending'")
            pending_count = cur.fetchone()['cnt']
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'requests': requests_list, 'pending_count': pending_count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/balance-requests/<int:request_id>/approve', methods=['POST'])
@perm('user_balance.approve')
def approve_balance_request(request_id):
    """Approve a balance request - creates finance transaction and deducts from payment method"""
    try:
        data = request.get_json() or {}
        notes = data.get('notes', '')
        payment_method_id = data.get('payment_method_id')
        
        if not payment_method_id:
            return jsonify({'success': False, 'error': 'Payment method is required'}), 400
        
        conn, cur = connection()
        
        # Get request details
        cur.execute("""
            SELECT ubt.*, u.name as user_name 
            FROM user_balance_transfers ubt
            JOIN user u ON ubt.to_user_id = u.id
            WHERE ubt.id = %s AND ubt.status = 'pending'
        """, (request_id,))
        req = cur.fetchone()
        
        if not req:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Request not found or already processed'}), 404
        
        to_user_id = req['to_user_id']
        amount = float(req['amount'])
        user_name_to = req['user_name']
        
        # Check payment method balance
        cur.execute("SELECT * FROM payment_methods WHERE id = %s", (payment_method_id,))
        pm = cur.fetchone()
        if not pm:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Payment method not found'}), 404
        
        pm_balance_before = float(pm['current_balance'])
        if pm_balance_before < amount:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': f'Insufficient balance in {pm["method_name"]}. Available: {pm_balance_before:.2f}, Requested: {amount:.2f}'}), 400
        
        pm_balance_after = pm_balance_before - amount
        
        # Get approver info
        approver_id = session.get('user_id')
        cur.execute("SELECT name FROM user WHERE id = %s", (approver_id,))
        approver_name = cur.fetchone()['name']
        
        # Generate transaction code
        import random
        transaction_code = f"FT-{random.randint(10000, 99999)}"
        cur.execute("SELECT id FROM finance_transactions WHERE transaction_code = %s", (transaction_code,))
        while cur.fetchone():
            transaction_code = f"FT-{random.randint(10000, 99999)}"
            cur.execute("SELECT id FROM finance_transactions WHERE transaction_code = %s", (transaction_code,))
        
        # Get serial number
        cur.execute("SELECT COALESCE(MAX(serial_number), 0) + 1 as next_serial FROM finance_transactions WHERE serial_number IS NOT NULL")
        serial_number = cur.fetchone()['next_serial']
        
        # Create finance transaction (Internal Transfer - expense from PM to user)
        from datetime import date
        cur.execute("""
            INSERT INTO finance_transactions
            (transaction_code, transaction_type, amount, payment_method_id, category_id,
             description, transaction_date, notes, status, serial_number,
             added_by, added_by_user_id, approved_by, approved_by_user_id, approved_at,
             balance_before, balance_after)
            VALUES (%s, 'expense', %s, %s, 16, %s, %s, %s, 'approved', %s, %s, %s, %s, %s, NOW(), %s, %s)
        """, (transaction_code, amount, payment_method_id,
              f"Balance transfer to {user_name_to} (Request {req['transfer_code']})",
              date.today(), notes, serial_number,
              approver_name, approver_id, approver_name, approver_id,
              pm_balance_before, pm_balance_after))
        
        trans_id = cur.lastrowid
        
        # Update payment method balance
        cur.execute("UPDATE payment_methods SET current_balance = %s, updated_at = NOW() WHERE id = %s",
                    (pm_balance_after, payment_method_id))
        
        # Log payment method balance change
        cur.execute("""
            INSERT INTO payment_method_balance_history
            (payment_method_id, change_type, change_amount, previous_balance, new_balance,
             transaction_id, description, created_by)
            VALUES (%s, 'expense', %s, %s, %s, %s, %s, %s)
        """, (payment_method_id, -amount, pm_balance_before, pm_balance_after, trans_id,
              f"Balance request {req['transfer_code']} to {user_name_to}", approver_name))
        
        # Log finance approval
        cur.execute("""
            INSERT INTO finance_approval_log
            (transaction_id, action, action_by, action_by_user_id, notes, previous_status, new_status)
            VALUES (%s, 'approved', %s, %s, %s, NULL, 'approved')
        """, (trans_id, approver_name, approver_id, f"Balance request {req['transfer_code']}"))
        
        # Update user balance
        cur.execute("SELECT COALESCE(balance, 0) as balance FROM user_finance_balances WHERE user_id = %s", (to_user_id,))
        result = cur.fetchone()
        balance_before = float(result['balance']) if result else 0
        balance_after = balance_before + amount
        
        cur.execute("""
            INSERT INTO user_finance_balances (user_id, balance)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE balance = balance + %s, last_updated = NOW()
        """, (to_user_id, amount, amount))
        
        # Update request status
        cur.execute("""
            UPDATE user_balance_transfers 
            SET status = 'approved', approved_by = %s, approved_at = NOW(), notes = %s
            WHERE id = %s
        """, (approver_id, notes, request_id))
        
        # Create user balance history record
        cur.execute("""
            INSERT INTO user_balance_history 
            (user_id, change_type, change_amount, balance_before, balance_after, reference_id, reference_type, description, created_by)
            VALUES (%s, 'request_approved', %s, %s, %s, %s, 'request', %s, %s)
        """, (to_user_id, amount, balance_before, balance_after, request_id,
              f"{req['description']} (from {pm['method_name']})", approver_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Request approved', 'new_balance': balance_after, 'transaction_code': transaction_code})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/balance-requests/<int:request_id>/reject', methods=['POST'])
@perm('user_balance.approve')
def reject_balance_request(request_id):
    """Reject a balance request"""
    try:
        data = request.get_json() or {}
        reason = data.get('reason', '')
        
        if not reason:
            return jsonify({'success': False, 'error': 'Rejection reason is required'}), 400
        
        conn, cur = connection()
        
        cur.execute("""
            UPDATE user_balance_transfers 
            SET status = 'rejected', approved_by = %s, approved_at = NOW(), rejection_reason = %s
            WHERE id = %s AND status = 'pending'
        """, (session.get('user_id'), reason, request_id))
        
        if cur.rowcount == 0:
            return jsonify({'success': False, 'error': 'Request not found or already processed'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Request rejected'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/pending-approvals', methods=['GET'])
@perm('finance_txn.view')
def get_all_pending_approvals():
    """Get all pending approvals (transactions + balance requests)"""
    try:
        conn, cur = connection()
        
        # Pending transactions
        cur.execute("""
            SELECT 
                ft.id,
                ft.transaction_code as code,
                ft.transaction_type as type,
                ft.amount,
                ft.description,
                ft.added_at as created_at,
                ft.added_by as requested_by,
                'transaction' as approval_type
            FROM finance_transactions ft
            WHERE ft.status = 'pending'
            ORDER BY ft.added_at DESC
        """)
        pending_transactions = cur.fetchall()
        
        # Pending balance requests
        cur.execute("""
            SELECT 
                ubt.id,
                ubt.transfer_code as code,
                ubt.transfer_type as type,
                ubt.amount,
                ubt.description,
                ubt.created_at,
                u.name as requested_by,
                'balance_request' as approval_type
            FROM user_balance_transfers ubt
            LEFT JOIN user u ON ubt.requested_by = u.id
            WHERE ubt.status = 'pending'
            ORDER BY ubt.created_at DESC
        """)
        pending_requests = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'pending_transactions': pending_transactions,
            'pending_balance_requests': pending_requests,
            'total_pending': len(pending_transactions) + len(pending_requests)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# USER EXPENSE TRACKING MODULE
# ============================================================================

@app.route('/my-expenses')
@perm('expense.view')
def my_expenses_page():
    """User expense tracking page"""
    if not session.get('user_id'):
        return redirect(url_for('login'))
    return render_template('my_expenses.html')


@app.route('/api/sales-requests-lookup', methods=['GET'])
def sales_requests_lookup():
    """Lightweight SR lookup for dropdowns - accessible to any authenticated user"""
    if 'user_id' not in session:
        return jsonify(error="Not authenticated"), 401
    try:
        conn, cur = connection()
        cur.execute("""
            SELECT sr.id, sr.title, sr.client_id, sr.company_id,
                   c.client_name, comp.company_name
            FROM sales_request sr
            LEFT JOIN client c ON sr.client_id = c.id
            LEFT JOIN company comp ON sr.company_id = comp.id
            ORDER BY sr.id DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(success=True, data=[
            {
                'id': r['id'],
                'title': r.get('title', ''),
                'client_id': r.get('client_id'),
                'company_id': r.get('company_id'),
                'client_name': r.get('client_name', ''),
                'company_name': r.get('company_name', '')
            } for r in rows
        ])
    except Exception as e:
        print(f"DEBUG: sales_requests_lookup error: {e}")
        return jsonify(success=False, error=str(e)), 500


@app.route('/api/my-expenses', methods=['GET'])
@perm('expense.view')
def get_my_expenses():
    """Get current user's expense tracking records"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'Not logged in'}), 401
        
        conn, cur = connection()
        
        # Get user's current balance
        cur.execute("""
            SELECT COALESCE(balance, 0) as balance 
            FROM user_finance_balances 
            WHERE user_id = %s
        """, (user_id,))
        balance_row = cur.fetchone()
        current_balance = float(balance_row['balance']) if balance_row else 0
        
        # Get all expense records for user
        status_filter = request.args.get('status', '')
        query = """
            SELECT 
                uet.*,
                s.supplier_name as supplier_display,
                u.name as approved_by_name,
                c.client_name as client_name,
                comp.company_name as company_name
            FROM user_expense_tracking uet
            LEFT JOIN supplier s ON uet.supplier_id = s.id
            LEFT JOIN user u ON uet.approved_by = u.id
            LEFT JOIN client c ON uet.client_id = c.id
            LEFT JOIN company comp ON uet.company_id = comp.id
            WHERE uet.user_id = %s
        """
        params = [user_id]
        
        if status_filter:
            query += " AND uet.status = %s"
            params.append(status_filter)
        
        query += " ORDER BY uet.created_at DESC"
        cur.execute(query, params)
        expenses = cur.fetchall()
        
        # Calculate future balance (current balance - sum of draft/submitted expenses)
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as pending_total
            FROM user_expense_tracking
            WHERE user_id = %s AND status IN ('draft', 'submitted')
        """, (user_id,))
        pending_row = cur.fetchone()
        pending_total = float(pending_row['pending_total']) if pending_row else 0
        future_balance = current_balance - pending_total
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'expenses': expenses,
            'current_balance': current_balance,
            'pending_total': pending_total,
            'future_balance': future_balance
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/my-expenses', methods=['POST'])
@perm('expense.create')
def add_my_expense():
    """Add new expense tracking record"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'Not logged in'}), 401
        
        data = request.get_json()
        supplier_id = data.get('supplier_id')
        supplier_name = data.get('supplier_name', '')
        amount = float(data.get('amount', 0))
        description = data.get('description', '')
        expense_date = data.get('expense_date')
        sales_request_id = data.get('sales_request_id')
        client_id = data.get('client_id')
        company_id = data.get('company_id')
        
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Amount must be greater than 0'}), 400
        
        if not expense_date:
            return jsonify({'success': False, 'error': 'Date is required'}), 400
        
        conn, cur = connection()
        
        # Generate tracking code
        import random
        tracking_code = f"EXP-{random.randint(10000, 99999)}"
        
        # Get current balance for calculation
        cur.execute("""
            SELECT COALESCE(balance, 0) as balance 
            FROM user_finance_balances 
            WHERE user_id = %s
        """, (user_id,))
        balance_row = cur.fetchone()
        current_balance = float(balance_row['balance']) if balance_row else 0
        
        # Calculate future balance after this expense
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as pending_total
            FROM user_expense_tracking
            WHERE user_id = %s AND status IN ('draft', 'submitted')
        """, (user_id,))
        pending_row = cur.fetchone()
        pending_total = float(pending_row['pending_total']) if pending_row else 0
        
        balance_before = current_balance - pending_total
        balance_after = balance_before - amount
        
        # Insert expense record
        cur.execute("""
            INSERT INTO user_expense_tracking 
            (user_id, tracking_code, supplier_id, supplier_name, sales_request_id, client_id, company_id, amount, description, expense_date, status, balance_before, balance_after)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft', %s, %s)
        """, (user_id, tracking_code, supplier_id, supplier_name, sales_request_id, client_id, company_id, amount, description, expense_date, balance_before, balance_after))
        
        expense_id = cur.lastrowid
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'expense_id': expense_id,
            'tracking_code': tracking_code,
            'message': 'Expense added successfully'
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/my-expenses/<int:expense_id>', methods=['PUT'])
@perm('expense.edit')
def update_my_expense(expense_id):
    """Update expense tracking record (only draft status)"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'Not logged in'}), 401
        
        data = request.get_json()
        
        conn, cur = connection()
        
        # Check ownership and status
        cur.execute("""
            SELECT * FROM user_expense_tracking 
            WHERE id = %s AND user_id = %s AND status = 'draft'
        """, (expense_id, user_id))
        expense = cur.fetchone()
        
        if not expense:
            return jsonify({'success': False, 'error': 'Expense not found or cannot be edited'}), 404
        
        # Update fields
        supplier_id = data.get('supplier_id', expense['supplier_id'])
        supplier_name = data.get('supplier_name', expense['supplier_name'])
        amount = float(data.get('amount', expense['amount']))
        description = data.get('description', expense['description'])
        expense_date = data.get('expense_date', expense['expense_date'])
        sales_request_id = data.get('sales_request_id', expense['sales_request_id'])
        client_id = data.get('client_id', expense['client_id'])
        company_id = data.get('company_id', expense['company_id'])
        
        # Recalculate balances
        cur.execute("""
            SELECT COALESCE(balance, 0) as balance 
            FROM user_finance_balances 
            WHERE user_id = %s
        """, (user_id,))
        balance_row = cur.fetchone()
        current_balance = float(balance_row['balance']) if balance_row else 0
        
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as pending_total
            FROM user_expense_tracking
            WHERE user_id = %s AND status IN ('draft', 'submitted') AND id != %s
        """, (user_id, expense_id))
        pending_row = cur.fetchone()
        pending_total = float(pending_row['pending_total']) if pending_row else 0
        
        balance_before = current_balance - pending_total
        balance_after = balance_before - amount
        
        cur.execute("""
            UPDATE user_expense_tracking 
            SET supplier_id = %s, supplier_name = %s, amount = %s, description = %s, 
                expense_date = %s, sales_request_id = %s, client_id = %s, company_id = %s,
                balance_before = %s, balance_after = %s
            WHERE id = %s
        """, (supplier_id, supplier_name, amount, description, expense_date, 
              sales_request_id, client_id, company_id,
              balance_before, balance_after, expense_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Expense updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/my-expenses/<int:expense_id>', methods=['DELETE'])
@perm('expense.delete')
def delete_my_expense(expense_id):
    """Delete expense tracking record (only draft status)"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'Not logged in'}), 401
        
        conn, cur = connection()
        
        cur.execute("""
            DELETE FROM user_expense_tracking 
            WHERE id = %s AND user_id = %s AND status = 'draft'
        """, (expense_id, user_id))
        
        if cur.rowcount == 0:
            return jsonify({'success': False, 'error': 'Expense not found or cannot be deleted'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Expense deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/my-expenses/submit', methods=['POST'])
@perm('expense.submit')
def submit_my_expenses():
    """Submit all draft expenses for approval"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'Not logged in'}), 401
        
        conn, cur = connection()
        
        # Get all draft expenses
        cur.execute("""
            SELECT id, amount FROM user_expense_tracking 
            WHERE user_id = %s AND status = 'draft'
        """, (user_id,))
        drafts = cur.fetchall()
        
        if not drafts:
            return jsonify({'success': False, 'error': 'No draft expenses to submit'}), 400
        
        # Get current balance
        cur.execute("""
            SELECT COALESCE(balance, 0) as balance 
            FROM user_finance_balances 
            WHERE user_id = %s
        """, (user_id,))
        balance_row = cur.fetchone()
        current_balance = float(balance_row['balance']) if balance_row else 0
        
        # Check if total doesn't exceed balance
        total_amount = sum(float(d['amount']) for d in drafts)
        
        # Get already submitted expenses
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as submitted_total
            FROM user_expense_tracking
            WHERE user_id = %s AND status = 'submitted'
        """, (user_id,))
        submitted_row = cur.fetchone()
        submitted_total = float(submitted_row['submitted_total']) if submitted_row else 0
        
        if total_amount + submitted_total > current_balance:
            return jsonify({
                'success': False, 
                'error': f'Total expenses ({total_amount + submitted_total:.2f}) exceed your balance ({current_balance:.2f})'
            }), 400
        
        # Update all drafts to submitted
        cur.execute("""
            UPDATE user_expense_tracking 
            SET status = 'submitted', submitted_at = NOW()
            WHERE user_id = %s AND status = 'draft'
        """, (user_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'{len(drafts)} expense(s) submitted for approval',
            'submitted_count': len(drafts)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/expense-approvals', methods=['GET'])
@perm('expense_tracking.view')
def get_expense_approvals():
    """Get all submitted expenses pending approval (admin/finance only)"""
    try:
        conn, cur = connection()
        
        status_filter = request.args.get('status', 'submitted')
        
        # Support fetching both submitted and manager_approved for finance page
        if status_filter == 'pending_finance':
            cur.execute("""
                SELECT 
                    uet.*,
                    u.name as user_name,
                    u.email as user_email,
                    s.supplier_name as supplier_display,
                    ufb.balance as user_current_balance,
                    approver.name as approved_by_name,
                    c.client_name as client_name,
                    comp.company_name as company_name
                FROM user_expense_tracking uet
                JOIN user u ON uet.user_id = u.id
                LEFT JOIN supplier s ON uet.supplier_id = s.id
                LEFT JOIN user_finance_balances ufb ON uet.user_id = ufb.user_id
                LEFT JOIN user approver ON uet.approved_by = approver.id
                LEFT JOIN client c ON uet.client_id = c.id
                LEFT JOIN company comp ON uet.company_id = comp.id
                WHERE uet.status IN ('submitted', 'manager_approved')
                ORDER BY uet.submitted_at DESC
            """)
        else:
            cur.execute("""
                SELECT 
                    uet.*,
                    u.name as user_name,
                    u.email as user_email,
                    s.supplier_name as supplier_display,
                    ufb.balance as user_current_balance,
                    approver.name as approved_by_name,
                    c.client_name as client_name,
                    comp.company_name as company_name
                FROM user_expense_tracking uet
                JOIN user u ON uet.user_id = u.id
                LEFT JOIN supplier s ON uet.supplier_id = s.id
                LEFT JOIN user_finance_balances ufb ON uet.user_id = ufb.user_id
                LEFT JOIN user approver ON uet.approved_by = approver.id
                LEFT JOIN client c ON uet.client_id = c.id
                LEFT JOIN company comp ON uet.company_id = comp.id
                WHERE uet.status = %s
                ORDER BY uet.submitted_at DESC
            """, (status_filter,))
        expenses = cur.fetchall()
        
        # Get count by status
        cur.execute("""
            SELECT status, COUNT(*) as count 
            FROM user_expense_tracking 
            GROUP BY status
        """)
        status_counts = {row['status']: row['count'] for row in cur.fetchall()}
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'expenses': expenses,
            'status_counts': status_counts
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/expense-approvals/<int:expense_id>/approve', methods=['POST'])
@perm('expense_tracking.approve_manager')
def approve_user_expense(expense_id):
    """Manager approval - sends to finance for final approval"""
    try:
        conn, cur = connection()
        data = request.get_json() or {}
        
        # Get expense details
        cur.execute("""
            SELECT * FROM user_expense_tracking 
            WHERE id = %s AND status = 'submitted'
        """, (expense_id,))
        expense = cur.fetchone()
        
        if not expense:
            return jsonify({'success': False, 'error': 'Expense not found or not pending approval'}), 404
        
        # Store requested amount and update with edited amount
        edited_amount = data.get('edited_amount')
        if edited_amount is not None:
            cur.execute("""
                UPDATE user_expense_tracking 
                SET requested_amount = amount, amount = %s
                WHERE id = %s
            """, (float(edited_amount), expense_id))
        
        # Update expense status to manager_approved (pending finance approval)
        cur.execute("""
            UPDATE user_expense_tracking 
            SET status = 'manager_approved', 
                manager_approved_by = %s, 
                manager_approved_at = NOW()
            WHERE id = %s
        """, (session.get('user_id'), expense_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Expense approved and sent to finance'})
        
    except Exception as e:
        print(f"Error approving expense: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/expense-approvals/<int:expense_id>/update-amount', methods=['POST'])
@perm('expense_tracking.edit_amount')
def update_expense_amount(expense_id):
    """Auto-save edited amount (works for both manager and finance editing)"""
    try:
        conn, cur = connection()
        data = request.get_json() or {}
        
        new_amount = data.get('amount')
        if new_amount is None:
            return jsonify({'success': False, 'error': 'Amount required'}), 400
        
        # Store requested amount if first edit, works for both submitted and manager_approved
        cur.execute("""
            UPDATE user_expense_tracking 
            SET requested_amount = COALESCE(requested_amount, amount), amount = %s
            WHERE id = %s AND status IN ('submitted', 'manager_approved')
        """, (float(new_amount), expense_id))
        
        if cur.rowcount == 0:
            return jsonify({'success': False, 'error': 'Expense not found or not pending'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error updating amount: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/expense-approvals/approve-bulk', methods=['POST'])
@perm('expense_tracking.approve_manager')
def approve_expenses_bulk():
    """Manager approval for multiple expenses - sends to finance"""
    try:
        conn, cur = connection()
        data = request.get_json() or {}
        
        expenses = data.get('expenses', [])
        if not expenses:
            return jsonify({'success': False, 'error': 'No expenses provided'}), 400
        
        approved_count = 0
        approver_id = session.get('user_id')
        
        for exp in expenses:
            exp_id = exp.get('id')
            amount = exp.get('amount')
            
            # Update amount and set to manager_approved
            cur.execute("""
                UPDATE user_expense_tracking 
                SET requested_amount = COALESCE(requested_amount, amount),
                    amount = %s,
                    status = 'manager_approved',
                    manager_approved_by = %s,
                    manager_approved_at = NOW()
                WHERE id = %s AND status = 'submitted'
            """, (float(amount), approver_id, exp_id))
            
            if cur.rowcount > 0:
                approved_count += 1
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'approved_count': approved_count})
        
    except Exception as e:
        print(f"Error bulk approving: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/expense-approvals/<int:expense_id>/finance-approve', methods=['POST'])
@perm('expense_tracking.approve_finance')
def finance_approve_user_expense(expense_id):
    """Final finance approval for user expense - creates finance transaction"""
    try:
        conn, cur = connection()
        data = request.get_json() or {}
        
        # Get expense details
        cur.execute("""
            SELECT uet.*, u.name as user_name
            FROM user_expense_tracking uet
            JOIN user u ON uet.user_id = u.id
            WHERE uet.id = %s AND uet.status = 'manager_approved'
        """, (expense_id,))
        expense = cur.fetchone()
        
        if not expense:
            return jsonify({'success': False, 'error': 'Expense not found or not pending finance approval'}), 404
        
        # Allow finance to edit amount
        final_amount = float(data.get('edited_amount', expense['amount']))
        
        # Update the user expense amount if changed
        if data.get('edited_amount') is not None:
            cur.execute("""
                UPDATE user_expense_tracking 
                SET requested_amount = COALESCE(requested_amount, amount), amount = %s
                WHERE id = %s
            """, (final_amount, expense_id))
        
        approver_id = session.get('user_id')
        cur.execute("SELECT name FROM user WHERE id = %s", (approver_id,))
        approver_name = cur.fetchone()['name']
        
        # Generate transaction code
        import random
        transaction_code = f"FT-{random.randint(10000, 99999)}"
        cur.execute("SELECT id FROM finance_transactions WHERE transaction_code = %s", (transaction_code,))
        while cur.fetchone():
            transaction_code = f"FT-{random.randint(10000, 99999)}"
            cur.execute("SELECT id FROM finance_transactions WHERE transaction_code = %s", (transaction_code,))
        
        # Get serial number
        cur.execute("SELECT COALESCE(MAX(serial_number), 0) + 1 as next_serial FROM finance_transactions WHERE serial_number IS NOT NULL")
        serial_number = cur.fetchone()['next_serial']
        
        # Default to Cash payment method (id=1) and Operational Expenses category (id=13)
        payment_method_id = 1
        category_id = 13  # Operational Expenses
        
        # Get payment method balance
        cur.execute("SELECT current_balance FROM payment_methods WHERE id = %s", (payment_method_id,))
        pm_row = cur.fetchone()
        balance_before = float(pm_row['current_balance']) if pm_row else 0
        balance_after = balance_before - final_amount
        
        # Create finance transaction
        cur.execute("""
            INSERT INTO finance_transactions
            (transaction_code, transaction_type, amount, payment_method_id, category_id,
             supplier_id, description, transaction_date, notes, status, serial_number,
             added_by, added_by_user_id, approved_by, approved_by_user_id, approved_at,
             balance_before, balance_after)
            VALUES (%s, 'expense', %s, %s, %s, %s, %s, %s, %s, 'approved', %s, %s, %s, %s, %s, NOW(), %s, %s)
        """, (transaction_code, final_amount, payment_method_id, category_id,
              expense['supplier_id'],
              f"User Expense: {expense['description']} (from {expense['tracking_code']})",
              expense['expense_date'],
              f"User expense by {expense['user_name']}",
              serial_number, approver_name, approver_id, approver_name, approver_id,
              balance_before, balance_after))
        
        trans_id = cur.lastrowid
        
        # Update payment method balance
        cur.execute("""
            UPDATE payment_methods 
            SET current_balance = %s, updated_at = NOW()
            WHERE id = %s
        """, (balance_after, payment_method_id))
        
        # Log balance change
        cur.execute("""
            INSERT INTO payment_method_balance_history
            (payment_method_id, change_type, change_amount, previous_balance, new_balance,
             transaction_id, description, created_by)
            VALUES (%s, 'expense', %s, %s, %s, %s, %s, %s)
        """, (payment_method_id, -final_amount, balance_before, balance_after, trans_id,
              f"User Expense {expense['tracking_code']}", approver_name))
        
        # Log approval
        cur.execute("""
            INSERT INTO finance_approval_log
            (transaction_id, action, action_by, action_by_user_id, notes, previous_status, new_status)
            VALUES (%s, 'approved', %s, %s, %s, NULL, 'approved')
        """, (trans_id, approver_name, approver_id, f"From user expense {expense['tracking_code']}"))
        
        # Update user expense status and link to transaction
        cur.execute("""
            UPDATE user_expense_tracking 
            SET status = 'approved', 
                approved_by = %s, 
                approved_at = NOW(),
                balance_before = %s,
                balance_after = %s
            WHERE id = %s
        """, (approver_id, balance_before, balance_after, expense_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Expense approved and transaction created', 'transaction_id': trans_id, 'transaction_code': transaction_code})
        
    except Exception as e:
        print(f"Error finance approving expense: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/expense-approvals/finance-approve-bulk', methods=['POST'])
@perm('expense_tracking.approve_finance')
def finance_approve_expenses_bulk():
    """Finance approval for multiple expenses - creates finance transactions with selected category"""
    try:
        conn, cur = connection()
        data = request.get_json() or {}
        
        expenses = data.get('expenses', [])
        if not expenses:
            return jsonify({'success': False, 'error': 'No expenses provided'}), 400
        
        approved_count = 0
        approver_id = session.get('user_id')
        cur.execute("SELECT name FROM user WHERE id = %s", (approver_id,))
        approver_name = cur.fetchone()['name']
        
        # Default payment method
        payment_method_id = 1  # Cash
        
        import random
        
        for exp in expenses:
            exp_id = exp.get('id')
            final_amount = float(exp.get('amount', 0))
            category_id = exp.get('category_id')  # Main expense category
            subcategory_id = exp.get('subcategory_id')  # Subcategory (if selected)
            
            if not category_id:
                continue  # Skip if no category selected
            
            category_id = int(category_id)
            subcategory_id = int(subcategory_id) if subcategory_id else None
            
            # Get expense details
            cur.execute("""
                SELECT uet.*, u.name as user_name
                FROM user_expense_tracking uet
                JOIN user u ON uet.user_id = u.id
                WHERE uet.id = %s AND uet.status IN ('submitted', 'manager_approved')
            """, (exp_id,))
            expense = cur.fetchone()
            
            if not expense:
                continue
            
            # ============================================
            # 1. Create INCOME transaction (Internal Transfer)
            # ============================================
            income_code = f"FT-{random.randint(10000, 99999)}"
            cur.execute("SELECT id FROM finance_transactions WHERE transaction_code = %s", (income_code,))
            while cur.fetchone():
                income_code = f"FT-{random.randint(10000, 99999)}"
                cur.execute("SELECT id FROM finance_transactions WHERE transaction_code = %s", (income_code,))
            
            cur.execute("SELECT COALESCE(MAX(serial_number), 0) + 1 as next_serial FROM finance_transactions WHERE serial_number IS NOT NULL")
            serial_number = cur.fetchone()['next_serial']
            
            cur.execute("SELECT current_balance FROM payment_methods WHERE id = %s", (payment_method_id,))
            pm_row = cur.fetchone()
            balance_before_income = float(pm_row['current_balance']) if pm_row else 0
            balance_after_income = balance_before_income + final_amount
            
            # Internal Transfer Income category ID = 44
            cur.execute("""
                INSERT INTO finance_transactions
                (transaction_code, transaction_type, amount, payment_method_id, category_id,
                 supplier_id, client_id, sales_request_id, description, transaction_date, notes, status, serial_number,
                 added_by, added_by_user_id, approved_by, approved_by_user_id, approved_at,
                 balance_before, balance_after)
                VALUES (%s, 'income', %s, %s, 44, %s, %s, %s, %s, %s, %s, 'approved', %s, %s, %s, %s, %s, NOW(), %s, %s)
            """, (income_code, final_amount, payment_method_id,
                  expense['supplier_id'],
                  expense.get('client_id'),
                  expense.get('sales_request_id'),
                  f"Internal Transfer - {expense['description']} ({expense['tracking_code']})",
                  expense['expense_date'],
                  f"User expense by {expense['user_name']}",
                  serial_number, approver_name, approver_id, approver_name, approver_id,
                  balance_before_income, balance_after_income))
            
            income_trans_id = cur.lastrowid
            
            # Update payment method balance after income
            cur.execute("UPDATE payment_methods SET current_balance = %s, updated_at = NOW() WHERE id = %s",
                        (balance_after_income, payment_method_id))
            
            # Log income balance change
            cur.execute("""
                INSERT INTO payment_method_balance_history
                (payment_method_id, change_type, change_amount, previous_balance, new_balance,
                 transaction_id, description, created_by)
                VALUES (%s, 'income', %s, %s, %s, %s, %s, %s)
            """, (payment_method_id, final_amount, balance_before_income, balance_after_income, income_trans_id,
                  f"User Expense Income {expense['tracking_code']}", approver_name))
            
            cur.execute("""
                INSERT INTO finance_approval_log
                (transaction_id, action, action_by, action_by_user_id, notes, previous_status, new_status)
                VALUES (%s, 'approved', %s, %s, %s, NULL, 'approved')
            """, (income_trans_id, approver_name, approver_id, f"Income from user expense {expense['tracking_code']}"))
            
            # ============================================
            # 2. Create EXPENSE transaction (selected category)
            # ============================================
            expense_code = f"FT-{random.randint(10000, 99999)}"
            cur.execute("SELECT id FROM finance_transactions WHERE transaction_code = %s", (expense_code,))
            while cur.fetchone():
                expense_code = f"FT-{random.randint(10000, 99999)}"
                cur.execute("SELECT id FROM finance_transactions WHERE transaction_code = %s", (expense_code,))
            
            serial_number += 1
            
            balance_before_expense = balance_after_income  # After income was added
            balance_after_expense = balance_before_expense - final_amount
            
            cur.execute("""
                INSERT INTO finance_transactions
                (transaction_code, transaction_type, amount, payment_method_id, category_id, subcategory_id,
                 supplier_id, client_id, sales_request_id, description, transaction_date, notes, status, serial_number,
                 added_by, added_by_user_id, approved_by, approved_by_user_id, approved_at,
                 balance_before, balance_after)
                VALUES (%s, 'expense', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved', %s, %s, %s, %s, %s, NOW(), %s, %s)
            """, (expense_code, final_amount, payment_method_id, category_id, subcategory_id,
                  expense['supplier_id'],
                  expense.get('client_id'),
                  expense.get('sales_request_id'),
                  f"User Expense: {expense['description']} ({expense['tracking_code']})",
                  expense['expense_date'],
                  f"User expense by {expense['user_name']}",
                  serial_number, approver_name, approver_id, approver_name, approver_id,
                  balance_before_expense, balance_after_expense))
            
            expense_trans_id = cur.lastrowid
            
            # Update payment method balance after expense
            cur.execute("UPDATE payment_methods SET current_balance = %s, updated_at = NOW() WHERE id = %s",
                        (balance_after_expense, payment_method_id))
            
            # Log expense balance change
            cur.execute("""
                INSERT INTO payment_method_balance_history
                (payment_method_id, change_type, change_amount, previous_balance, new_balance,
                 transaction_id, description, created_by)
                VALUES (%s, 'expense', %s, %s, %s, %s, %s, %s)
            """, (payment_method_id, -final_amount, balance_before_expense, balance_after_expense, expense_trans_id,
                  f"User Expense {expense['tracking_code']}", approver_name))
            
            cur.execute("""
                INSERT INTO finance_approval_log
                (transaction_id, action, action_by, action_by_user_id, notes, previous_status, new_status)
                VALUES (%s, 'approved', %s, %s, %s, NULL, 'approved')
            """, (expense_trans_id, approver_name, approver_id, f"Expense from user expense {expense['tracking_code']}"))
            
            # Update user expense status
            cur.execute("""
                UPDATE user_expense_tracking 
                SET requested_amount = COALESCE(requested_amount, amount),
                    amount = %s,
                    status = 'approved',
                    approved_by = %s,
                    approved_at = NOW(),
                    balance_before = %s,
                    balance_after = %s
                WHERE id = %s
            """, (final_amount, approver_id, balance_before_income, balance_after_expense, exp_id))
            
            # ============================================
            # 3. Deduct from user's personal balance
            # ============================================
            user_id = expense['user_id']
            cur.execute("SELECT COALESCE(balance, 0) as balance FROM user_finance_balances WHERE user_id = %s", (user_id,))
            ub_row = cur.fetchone()
            user_balance_before = float(ub_row['balance']) if ub_row else 0
            user_balance_after = user_balance_before - final_amount
            
            # Update user balance
            cur.execute("""
                INSERT INTO user_finance_balances (user_id, balance)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE balance = %s, last_updated = NOW()
            """, (user_id, user_balance_after, user_balance_after))
            
            # Log the balance change in user_balance_history
            cur.execute("""
                INSERT INTO user_balance_history 
                (user_id, change_type, change_amount, balance_before, balance_after, 
                 reference_id, reference_type, description, created_by)
                VALUES (%s, 'expense', %s, %s, %s, %s, 'user_expense', %s, %s)
            """, (user_id, -final_amount, user_balance_before, user_balance_after,
                  exp_id, f"Expense approved: {expense['description']} ({expense['tracking_code']})",
                  approver_id))
            
            approved_count += 1
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'approved_count': approved_count})
        
    except Exception as e:
        print(f"Error bulk finance approving: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/expense-approvals/reject-bulk', methods=['POST'])
@perm('expense_tracking.reject')
def reject_expenses_bulk():
    """Reject multiple expenses at once (works for both manager and finance rejection)"""
    try:
        conn, cur = connection()
        data = request.get_json() or {}
        
        expense_ids = data.get('expense_ids', [])
        reason = data.get('reason', '')
        
        if not expense_ids:
            return jsonify({'success': False, 'error': 'No expenses provided'}), 400
        
        rejected_count = 0
        rejector_id = session.get('user_id')
        
        for exp_id in expense_ids:
            # Can reject expenses with submitted OR manager_approved status
            cur.execute("""
                UPDATE user_expense_tracking 
                SET status = 'rejected',
                    rejected_by = %s,
                    rejected_at = NOW(),
                    rejection_reason = %s
                WHERE id = %s AND status IN ('submitted', 'manager_approved')
            """, (rejector_id, reason, exp_id))
            
            if cur.rowcount > 0:
                rejected_count += 1
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'rejected_count': rejected_count})
        
    except Exception as e:
        print(f"Error bulk rejecting: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/expense-approvals/<int:expense_id>/reject', methods=['POST'])
@perm('expense_tracking.reject')
def reject_user_expense(expense_id):
    """Reject user expense"""
    try:
        data = request.get_json() or {}
        reason = data.get('reason', '')
        
        if not reason:
            return jsonify({'success': False, 'error': 'Rejection reason is required'}), 400
        
        conn, cur = connection()
        
        cur.execute("""
            UPDATE user_expense_tracking 
            SET status = 'rejected', approved_by = %s, approved_at = NOW(), rejection_reason = %s
            WHERE id = %s AND status = 'submitted'
        """, (session.get('user_id'), reason, expense_id))
        
        if cur.rowcount == 0:
            return jsonify({'success': False, 'error': 'Expense not found or not pending approval'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Expense rejected'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# LOAN MANAGEMENT APIs
# ============================================================================

@app.route('/api/finance/users', methods=['GET'])
@perm('loan.view')
def get_all_users_for_loans():
    """Get all users for loan selection"""
    try:
        conn, cur = connection()
        cur.execute("""
            SELECT u.id, u.username, u.name,
                   COALESCE(ul.current_balance, 0) as loan_balance
            FROM user u
            LEFT JOIN user_loans ul ON u.id = ul.user_id
            ORDER BY u.name
        """)
        users = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'users': [{
                'id': u['id'],
                'username': u['username'],
                'name': u['name'],
                'loan_balance': float(u['loan_balance'] or 0)
            } for u in users]
        })
    except Exception as e:
        print(f"Error getting users: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/loans', methods=['GET'])
@perm('loan.view')
def get_all_loans():
    """Get all user loans summary"""
    try:
        conn, cur = connection()
        cur.execute("""
            SELECT ul.*, u.name as user_name, u.username
            FROM user_loans ul
            JOIN user u ON ul.user_id = u.id
            WHERE ul.current_balance > 0 OR ul.total_loan_amount > 0
            ORDER BY ul.current_balance DESC
        """)
        loans = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'loans': [{
                'user_id': l['user_id'],
                'user_name': l['user_name'],
                'username': l['username'],
                'total_loan_amount': float(l['total_loan_amount'] or 0),
                'total_paid_amount': float(l['total_paid_amount'] or 0),
                'current_balance': float(l['current_balance'] or 0)
            } for l in loans]
        })
    except Exception as e:
        print(f"Error getting loans: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/loans/<int:user_id>', methods=['GET'])
@perm('loan.view')
def get_user_loan_details(user_id):
    """Get detailed loan info for a specific user including transaction history"""
    try:
        conn, cur = connection()
        
        # Get user info and loan summary
        cur.execute("""
            SELECT u.id, u.name, u.username,
                   COALESCE(ul.total_loan_amount, 0) as total_loan_amount,
                   COALESCE(ul.total_paid_amount, 0) as total_paid_amount,
                   COALESCE(ul.current_balance, 0) as current_balance
            FROM user u
            LEFT JOIN user_loans ul ON u.id = ul.user_id
            WHERE u.id = %s
        """, (user_id,))
        user = cur.fetchone()
        
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        # Get loan transactions history
        cur.execute("""
            SELECT ult.*, ft.transaction_code
            FROM user_loan_transactions ult
            LEFT JOIN finance_transactions ft ON ult.finance_transaction_id = ft.id
            WHERE ult.user_id = %s
            ORDER BY ult.created_at DESC
        """, (user_id,))
        transactions = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'name': user['name'],
                'username': user['username']
            },
            'loan_summary': {
                'total_loan_amount': float(user['total_loan_amount'] or 0),
                'total_paid_amount': float(user['total_paid_amount'] or 0),
                'current_balance': float(user['current_balance'] or 0)
            },
            'transactions': [{
                'id': t['id'],
                'transaction_type': t['transaction_type'],
                'amount': float(t['amount']),
                'balance_before': float(t['balance_before'] or 0),
                'balance_after': float(t['balance_after'] or 0),
                'notes': t['notes'],
                'transaction_code': t['transaction_code'],
                'created_by': t['created_by'],
                'created_at': t['created_at'].isoformat() if t['created_at'] else None
            } for t in transactions]
        })
    except Exception as e:
        print(f"Error getting user loan details: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/finance/loans/add', methods=['POST'])
@perm('loan.create')
def add_loan_transaction():
    """Add a new loan (expense) or pay loan (income) transaction"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        loan_user_id = data.get('loan_user_id')
        amount = float(data.get('amount', 0))
        loan_type = data.get('loan_type')  # 'loan' or 'pay_loan'
        payment_method_id = data.get('payment_method_id')
        description = data.get('description', '')
        transaction_date = data.get('transaction_date')
        
        if not loan_user_id or not amount or amount <= 0:
            return jsonify({'success': False, 'error': 'User and amount are required'}), 400
        
        if loan_type not in ['loan', 'pay_loan']:
            return jsonify({'success': False, 'error': 'Invalid loan type'}), 400
        
        if not payment_method_id:
            return jsonify({'success': False, 'error': 'Payment method is required'}), 400
        
        conn, cur = connection()
        
        # Get user info
        cur.execute("SELECT id, name FROM user WHERE id = %s", (loan_user_id,))
        loan_user = cur.fetchone()
        if not loan_user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        # Get current loan balance
        cur.execute("""
            SELECT COALESCE(current_balance, 0) as balance 
            FROM user_loans WHERE user_id = %s
        """, (loan_user_id,))
        loan_record = cur.fetchone()
        current_balance = float(loan_record['balance']) if loan_record else 0
        
        # Validate pay_loan doesn't exceed current balance
        if loan_type == 'pay_loan' and amount > current_balance:
            return jsonify({
                'success': False, 
                'error': f'Pay loan amount ({amount}) cannot exceed current loan balance ({current_balance})'
            }), 400
        
        # Determine transaction type and category
        if loan_type == 'loan':
            transaction_type = 'expense'
            category_code = 'LOAN'
            new_balance = current_balance + amount
        else:
            transaction_type = 'income'
            category_code = 'PAY_LOAN'
            new_balance = current_balance - amount
        
        # Get category ID
        cur.execute("SELECT id FROM finance_categories WHERE category_code = %s", (category_code,))
        cat = cur.fetchone()
        if not cat:
            return jsonify({'success': False, 'error': f'Category {category_code} not found'}), 500
        category_id = cat['id']
        
        # Generate transaction code
        trans_code = f"FIN-{uuid.uuid4().hex[:8].upper()}"
        
        # Build description with user info
        full_description = f"{loan_type.replace('_', ' ').title()} - {loan_user['name']}"
        if description:
            full_description += f": {description}"
        
        # For admin/finance users, directly approve the transaction
        user_name = session.get('username', 'System')
        status = 'approved'
        
        # Get next serial number for approved transactions
        cur.execute("SELECT COALESCE(MAX(serial_number), 0) + 1 as next_serial FROM finance_transactions WHERE serial_number IS NOT NULL")
        next_serial = cur.fetchone()['next_serial']
        
        # Get payment method balance
        cur.execute("SELECT current_balance FROM payment_methods WHERE id = %s", (payment_method_id,))
        pm = cur.fetchone()
        if not pm:
            return jsonify({'success': False, 'error': 'Payment method not found'}), 404
        
        pm_balance_before = float(pm['current_balance'])
        
        # Calculate new payment method balance
        if transaction_type == 'expense':
            pm_balance_after = pm_balance_before - amount
        else:
            pm_balance_after = pm_balance_before + amount
        
        # Insert finance transaction
        cur.execute("""
            INSERT INTO finance_transactions 
            (transaction_code, transaction_type, amount, payment_method_id, category_id,
             description, transaction_date, status, serial_number, loan_user_id,
             added_by, added_by_user_id, added_at, 
             approved_by, approved_by_user_id, approved_at,
             balance_before, balance_after)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, NOW(), %s, %s)
        """, (trans_code, transaction_type, amount, payment_method_id, category_id,
              full_description, transaction_date or date.today(), status, next_serial, loan_user_id,
              user_name, session.get('user_id'),
              user_name, session.get('user_id'),
              pm_balance_before, pm_balance_after))
        
        finance_trans_id = cur.lastrowid
        
        # Update payment method balance
        cur.execute("""
            UPDATE payment_methods SET current_balance = %s WHERE id = %s
        """, (pm_balance_after, payment_method_id))
        
        # Record payment method balance history
        cur.execute("""
            INSERT INTO payment_method_balance_history 
            (payment_method_id, amount, balance_before, balance_after, 
             change_type, reference_type, reference_id, notes, changed_by, changed_by_user_id)
            VALUES (%s, %s, %s, %s, %s, 'finance_transaction', %s, %s, %s, %s)
        """, (payment_method_id, amount if transaction_type == 'income' else -amount,
              pm_balance_before, pm_balance_after,
              'credit' if transaction_type == 'income' else 'debit',
              finance_trans_id, full_description, user_name, session.get('user_id')))
        
        # Create or update user_loans record
        cur.execute("""
            INSERT INTO user_loans (user_id, total_loan_amount, total_paid_amount, current_balance)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                total_loan_amount = total_loan_amount + %s,
                total_paid_amount = total_paid_amount + %s,
                current_balance = %s
        """, (
            loan_user_id,
            amount if loan_type == 'loan' else 0,
            amount if loan_type == 'pay_loan' else 0,
            new_balance,
            amount if loan_type == 'loan' else 0,
            amount if loan_type == 'pay_loan' else 0,
            new_balance
        ))
        
        # Record loan transaction
        cur.execute("""
            INSERT INTO user_loan_transactions 
            (user_id, finance_transaction_id, transaction_type, amount, 
             balance_before, balance_after, notes, created_by, created_by_user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (loan_user_id, finance_trans_id, loan_type, amount,
              current_balance, new_balance, description, user_name, session.get('user_id')))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'{"Loan" if loan_type == "loan" else "Pay Loan"} transaction added successfully',
            'transaction_code': trans_code,
            'serial_number': next_serial,
            'new_loan_balance': new_balance
        })
        
    except Exception as e:
        print(f"Error adding loan transaction: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# EXPENSE TRACKING MODULE | نظام تتبع المصروفات
# ============================================================================

def generate_tracking_code():
    """Generate unique expense tracking code"""
    import random
    import string
    return 'EXP-' + ''.join(random.choices(string.digits, k=6))


@app.route('/expense-tracking', methods=['GET'])
@perm('expense_tracking.view')
def expense_tracking_page():
    """Render expense tracking submission page"""
    return render_template('expense_tracking.html')


@app.route('/expense-tracking-approval', methods=['GET'])
@perm('expense_tracking.approve_manager')
def expense_tracking_approval_page():
    """Render expense tracking approval page (first level - manager)"""
    return render_template('expense_tracking_approval.html')


@app.route('/finance-expense-approval', methods=['GET'])
@perm('expense_tracking.approve_finance')
def finance_expense_approval_page():
    """Render finance expense approval page (second level - finance)"""
    return render_template('finance_expense_approval.html')


@app.route('/api/expense-tracking', methods=['GET'])
@perm('expense_tracking.view')
def get_expense_trackings():
    """Get expense tracking records"""
    try:
        status = request.args.get('status')
        user_only = request.args.get('user_only', 'false').lower() == 'true'
        
        conn, cur = connection()
        
        query = """
            SELECT et.*, pm.method_name as payment_method_name,
                   (SELECT COUNT(*) FROM expense_tracking_items WHERE tracking_id = et.id) as item_count
            FROM expense_tracking et
            LEFT JOIN payment_methods pm ON et.payment_method_id = pm.id
            WHERE 1=1
        """
        # Scope is authoritative: the caller no longer chooses their own breadth
        # via ?user_only. A member sees their own claims, a team leader their
        # team's, a head their department's, finance everything.
        scope_sql, params = scope_clause('expense_tracking.view', 'et.user_id')
        query += scope_sql

        if user_only:
            query += " AND et.user_id = %s"
            params.append(session.get('user_id'))

        if status:
            if status == 'manager_pending':
                query += " AND et.status = 'pending'"
            elif status == 'finance_pending':
                query += " AND et.status = 'manager_approved'"
            else:
                query += " AND et.status = %s"
                params.append(status)
        
        query += " ORDER BY et.created_at DESC"
        
        cur.execute(query, tuple(params))
        trackings = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'trackings': [{
                'id': t['id'],
                'tracking_code': t['tracking_code'],
                'user_name': t['user_name'],
                'total_amount': float(t['total_amount']),
                'description': t['description'],
                'tracking_date': t['tracking_date'].isoformat() if t['tracking_date'] else None,
                'payment_method_name': t['payment_method_name'],
                'status': t['status'],
                'item_count': t['item_count'],
                'manager_approved_by': t['manager_approved_by'],
                'manager_approved_at': t['manager_approved_at'].isoformat() if t['manager_approved_at'] else None,
                'finance_approved_by': t['finance_approved_by'],
                'finance_approved_at': t['finance_approved_at'].isoformat() if t['finance_approved_at'] else None,
                'created_at': t['created_at'].isoformat() if t['created_at'] else None
            } for t in trackings]
        })
    except Exception as e:
        print(f"Error getting expense trackings: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/expense-tracking/<int:tracking_id>', methods=['GET'])
@perm('expense_tracking.view')
def get_expense_tracking_details(tracking_id):
    """Get expense tracking details with items"""
    try:
        conn, cur = connection()
        
        # Get tracking
        cur.execute("""
            SELECT et.*, pm.method_name as payment_method_name
            FROM expense_tracking et
            LEFT JOIN payment_methods pm ON et.payment_method_id = pm.id
            WHERE et.id = %s
        """, (tracking_id,))
        tracking = cur.fetchone()
        
        if not tracking:
            return jsonify({'success': False, 'error': 'Tracking not found'}), 404
        
        # Get items
        cur.execute("""
            SELECT eti.*, 
                   fc.category_name,
                   fsc.category_name as subcategory_name
            FROM expense_tracking_items eti
            LEFT JOIN finance_categories fc ON eti.category_id = fc.id
            LEFT JOIN finance_categories fsc ON eti.subcategory_id = fsc.id
            WHERE eti.tracking_id = %s
            ORDER BY eti.id
        """, (tracking_id,))
        items = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'tracking': {
                'id': tracking['id'],
                'tracking_code': tracking['tracking_code'],
                'user_id': tracking['user_id'],
                'user_name': tracking['user_name'],
                'total_amount': float(tracking['total_amount']),
                'description': tracking['description'],
                'notes': tracking['notes'],
                'tracking_date': tracking['tracking_date'].isoformat() if tracking['tracking_date'] else None,
                'payment_method_id': tracking['payment_method_id'],
                'payment_method_name': tracking['payment_method_name'],
                'status': tracking['status'],
                'manager_approved_by': tracking['manager_approved_by'],
                'manager_approved_at': tracking['manager_approved_at'].isoformat() if tracking['manager_approved_at'] else None,
                'manager_notes': tracking['manager_notes'],
                'finance_approved_by': tracking['finance_approved_by'],
                'finance_approved_at': tracking['finance_approved_at'].isoformat() if tracking['finance_approved_at'] else None,
                'finance_notes': tracking['finance_notes'],
                'rejected_by': tracking['rejected_by'],
                'rejection_reason': tracking['rejection_reason'],
                'created_at': tracking['created_at'].isoformat() if tracking['created_at'] else None
            },
            'items': [{
                'id': i['id'],
                'item_description': i['item_description'],
                'amount': float(i['amount']),
                'category_id': i['category_id'],
                'category_name': i['category_name'],
                'subcategory_id': i['subcategory_id'],
                'subcategory_name': i['subcategory_name'],
                'notes': i['notes']
            } for i in items]
        })
    except Exception as e:
        print(f"Error getting expense tracking details: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/expense-tracking', methods=['POST'])
@perm('expense_tracking.create')
def create_expense_tracking():
    """Create new expense tracking submission"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        
        items = data.get('items', [])
        description = data.get('description', '')
        notes = data.get('notes', '')
        tracking_date = data.get('tracking_date', datetime.now().strftime('%Y-%m-%d'))
        payment_method_id = data.get('payment_method_id')
        
        if not items or len(items) == 0:
            return jsonify({'success': False, 'error': 'At least one expense item is required'}), 400
        
        # Calculate total
        total_amount = sum(float(item.get('amount', 0)) for item in items)
        
        if total_amount <= 0:
            return jsonify({'success': False, 'error': 'Total amount must be greater than zero'}), 400
        
        conn, cur = connection()
        
        # Generate unique tracking code
        tracking_code = generate_tracking_code()
        cur.execute("SELECT id FROM expense_tracking WHERE tracking_code = %s", (tracking_code,))
        while cur.fetchone():
            tracking_code = generate_tracking_code()
            cur.execute("SELECT id FROM expense_tracking WHERE tracking_code = %s", (tracking_code,))
        
        user_name = session.get('name', session.get('username', 'Unknown'))
        user_id = session.get('user_id')
        
        # Insert tracking record
        cur.execute("""
            INSERT INTO expense_tracking 
            (tracking_code, user_id, user_name, total_amount, description, notes, 
             tracking_date, payment_method_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (tracking_code, user_id, user_name, total_amount, description, notes,
              tracking_date, payment_method_id))
        
        tracking_id = cur.lastrowid
        
        # Insert items
        for item in items:
            cur.execute("""
                INSERT INTO expense_tracking_items (tracking_id, item_description, amount, notes)
                VALUES (%s, %s, %s, %s)
            """, (tracking_id, item.get('description', ''), float(item.get('amount', 0)), item.get('notes', '')))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Expense tracking submitted for approval',
            'tracking_id': tracking_id,
            'tracking_code': tracking_code
        })
    except Exception as e:
        print(f"Error creating expense tracking: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/expense-tracking/<int:tracking_id>/manager-approve', methods=['POST'])
@perm('expense_tracking.approve_manager')
def manager_approve_expense_tracking(tracking_id):
    """First level approval by manager/admin"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json() or {}
        notes = data.get('notes', '')
        
        conn, cur = connection()
        
        # Check status
        cur.execute("SELECT status FROM expense_tracking WHERE id = %s", (tracking_id,))
        tracking = cur.fetchone()
        
        if not tracking:
            return jsonify({'success': False, 'error': 'Tracking not found'}), 404
        
        if tracking['status'] != 'pending':
            return jsonify({'success': False, 'error': f'Cannot approve: status is {tracking["status"]}'}), 400
        
        user_name = session.get('name', session.get('username', 'System'))
        user_id = session.get('user_id')
        
        # Update to manager_approved
        cur.execute("""
            UPDATE expense_tracking 
            SET status = 'manager_approved',
                manager_approved_by = %s,
                manager_approved_by_user_id = %s,
                manager_approved_at = NOW(),
                manager_notes = %s
            WHERE id = %s
        """, (user_name, user_id, notes, tracking_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Expense tracking approved and sent to finance for final approval'
        })
    except Exception as e:
        print(f"Error in manager approval: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/expense-tracking/<int:tracking_id>/update-total', methods=['POST'])
@perm('expense_tracking.edit_amount')
def update_expense_tracking_total(tracking_id):
    """Update total amount of expense tracking (finance can edit before approval)"""
    try:
        conn, cur = connection()
        data = request.get_json() or {}
        
        new_total = data.get('total_amount')
        if new_total is None:
            return jsonify({'success': False, 'error': 'Total amount required'}), 400
        
        # Store original total and update
        cur.execute("""
            UPDATE expense_tracking 
            SET original_total_amount = COALESCE(original_total_amount, total_amount),
                total_amount = %s
            WHERE id = %s AND status = 'manager_approved'
        """, (float(new_total), tracking_id))
        
        if cur.rowcount == 0:
            return jsonify({'success': False, 'error': 'Tracking not found or not pending finance approval'}), 404
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error updating tracking total: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/expense-tracking/<int:tracking_id>/finance-approve', methods=['POST'])
@perm('expense_tracking.approve_finance')
def finance_approve_expense_tracking(tracking_id):
    """Second level approval by finance - assigns categories and creates transactions"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json() or {}
        notes = data.get('notes', '')
        items_categories = data.get('items', [])  # [{item_id, category_id, subcategory_id}, ...]
        
        conn, cur = connection()
        
        # Get tracking with items
        cur.execute("""
            SELECT et.*, pm.method_name 
            FROM expense_tracking et
            LEFT JOIN payment_methods pm ON et.payment_method_id = pm.id
            WHERE et.id = %s
        """, (tracking_id,))
        tracking = cur.fetchone()
        
        if not tracking:
            return jsonify({'success': False, 'error': 'Tracking not found'}), 404
        
        if tracking['status'] != 'manager_approved':
            return jsonify({'success': False, 'error': f'Cannot approve: status is {tracking["status"]}'}), 400
        
        # Validate all items have categories
        cur.execute("SELECT * FROM expense_tracking_items WHERE tracking_id = %s", (tracking_id,))
        items = cur.fetchall()
        
        if len(items_categories) != len(items):
            return jsonify({'success': False, 'error': 'All items must have categories assigned'}), 400
        
        # Build items map
        items_map = {str(ic['item_id']): ic for ic in items_categories}
        
        for item in items:
            if str(item['id']) not in items_map:
                return jsonify({'success': False, 'error': f'Category required for item: {item["item_description"]}'}), 400
            if not items_map[str(item['id'])].get('category_id'):
                return jsonify({'success': False, 'error': f'Category required for item: {item["item_description"]}'}), 400
        
        user_name = session.get('name', session.get('username', 'System'))
        user_id = session.get('user_id')
        total_amount = float(tracking['total_amount'])
        payment_method_id = tracking['payment_method_id']
        
        # Get current payment method balance
        cur.execute("SELECT current_balance FROM payment_methods WHERE id = %s", (payment_method_id,))
        pm_row = cur.fetchone()
        if not pm_row:
            return jsonify({'success': False, 'error': 'Payment method not found'}), 400
        
        current_balance = float(pm_row['current_balance'])
        
        # Generate serial numbers
        cur.execute("SELECT COALESCE(MAX(serial_number), 0) as max_serial FROM finance_transactions WHERE serial_number IS NOT NULL")
        max_serial = cur.fetchone()['max_serial']
        next_serial = max_serial + 1
        
        # ============================================
        # 1. Create INCOME transaction (Internal Transfer)
        # ============================================
        income_code = generate_transaction_code()
        cur.execute("SELECT id FROM finance_transactions WHERE transaction_code = %s", (income_code,))
        while cur.fetchone():
            income_code = generate_transaction_code()
            cur.execute("SELECT id FROM finance_transactions WHERE transaction_code = %s", (income_code,))
        
        balance_after_income = current_balance + total_amount
        
        # Internal Transfer Income category ID = 44
        cur.execute("""
            INSERT INTO finance_transactions
            (transaction_code, transaction_type, amount, payment_method_id, category_id,
             description, transaction_date, status, serial_number, added_by, added_by_user_id,
             approved_by, approved_by_user_id, approved_at, balance_before, balance_after)
            VALUES (%s, 'income', %s, %s, 44, %s, %s, 'approved', %s, %s, %s, %s, %s, NOW(), %s, %s)
        """, (income_code, total_amount, payment_method_id,
              f'Internal Transfer - Expense Tracking {tracking["tracking_code"]}',
              tracking['tracking_date'], next_serial, user_name, user_id, user_name, user_id,
              current_balance, balance_after_income))
        
        income_trans_id = cur.lastrowid
        next_serial += 1
        
        # Log income transaction
        cur.execute("""
            INSERT INTO finance_approval_log
            (transaction_id, action, action_by, action_by_user_id, notes, previous_status, new_status)
            VALUES (%s, 'approved', %s, %s, 'Auto-created from expense tracking', NULL, 'approved')
        """, (income_trans_id, user_name, user_id))
        
        # ============================================
        # 2. Create EXPENSE transactions for each item
        # ============================================
        running_balance = balance_after_income
        
        for item in items:
            item_id = item['id']
            item_cat = items_map[str(item_id)]
            item_amount = float(item['amount'])
            category_id = item_cat.get('category_id')
            subcategory_id = item_cat.get('subcategory_id')
            
            # Update item with category
            cur.execute("""
                UPDATE expense_tracking_items 
                SET category_id = %s, subcategory_id = %s
                WHERE id = %s
            """, (category_id, subcategory_id, item_id))
            
            # Create expense transaction
            expense_code = generate_transaction_code()
            cur.execute("SELECT id FROM finance_transactions WHERE transaction_code = %s", (expense_code,))
            while cur.fetchone():
                expense_code = generate_transaction_code()
                cur.execute("SELECT id FROM finance_transactions WHERE transaction_code = %s", (expense_code,))
            
            balance_after_expense = running_balance - item_amount
            
            cur.execute("""
                INSERT INTO finance_transactions
                (transaction_code, transaction_type, amount, payment_method_id, category_id, subcategory_id,
                 description, transaction_date, status, serial_number, added_by, added_by_user_id,
                 approved_by, approved_by_user_id, approved_at, balance_before, balance_after)
                VALUES (%s, 'expense', %s, %s, %s, %s, %s, %s, 'approved', %s, %s, %s, %s, %s, NOW(), %s, %s)
            """, (expense_code, item_amount, payment_method_id, category_id, subcategory_id,
                  f'{item["item_description"]} - {tracking["tracking_code"]}',
                  tracking['tracking_date'], next_serial, user_name, user_id, user_name, user_id,
                  running_balance, balance_after_expense))
            
            expense_trans_id = cur.lastrowid
            
            # Update item with transaction reference
            cur.execute("UPDATE expense_tracking_items SET expense_transaction_id = %s WHERE id = %s", 
                        (expense_trans_id, item_id))
            
            # Log expense transaction
            cur.execute("""
                INSERT INTO finance_approval_log
                (transaction_id, action, action_by, action_by_user_id, notes, previous_status, new_status)
                VALUES (%s, 'approved', %s, %s, 'Auto-created from expense tracking', NULL, 'approved')
            """, (expense_trans_id, user_name, user_id))
            
            running_balance = balance_after_expense
            next_serial += 1
        
        # ============================================
        # 3. Update payment method balance (net effect is 0 since income = sum of expenses)
        # ============================================
        # The running_balance should equal current_balance since income = sum(expenses)
        cur.execute("""
            UPDATE payment_methods SET current_balance = %s WHERE id = %s
        """, (running_balance, payment_method_id))
        
        # ============================================
        # 4. Update expense tracking status
        # ============================================
        cur.execute("""
            UPDATE expense_tracking 
            SET status = 'approved',
                finance_approved_by = %s,
                finance_approved_by_user_id = %s,
                finance_approved_at = NOW(),
                finance_notes = %s,
                income_transaction_id = %s
            WHERE id = %s
        """, (user_name, user_id, notes, income_trans_id, tracking_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Expense tracking approved. Finance transactions created.',
            'income_transaction_id': income_trans_id
        })
    except Exception as e:
        print(f"Error in finance approval: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/expense-tracking/<int:tracking_id>/reject', methods=['POST'])
@perm('expense_tracking.reject')
def reject_expense_tracking(tracking_id):
    """Reject expense tracking at any stage"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json() or {}
        reason = data.get('reason', '')
        
        if not reason:
            return jsonify({'success': False, 'error': 'Rejection reason is required'}), 400
        
        conn, cur = connection()
        
        cur.execute("SELECT status FROM expense_tracking WHERE id = %s", (tracking_id,))
        tracking = cur.fetchone()
        
        if not tracking:
            return jsonify({'success': False, 'error': 'Tracking not found'}), 404
        
        if tracking['status'] in ['approved', 'rejected']:
            return jsonify({'success': False, 'error': f'Cannot reject: status is {tracking["status"]}'}), 400
        
        user_name = session.get('name', session.get('username', 'System'))
        user_id = session.get('user_id')
        
        cur.execute("""
            UPDATE expense_tracking 
            SET status = 'rejected',
                rejected_by = %s,
                rejected_by_user_id = %s,
                rejected_at = NOW(),
                rejection_reason = %s
            WHERE id = %s
        """, (user_name, user_id, reason, tracking_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Expense tracking rejected'
        })
    except Exception as e:
        print(f"Error rejecting expense tracking: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/expense-tracking/<int:tracking_id>/update-items', methods=['POST'])
@perm('expense_tracking.edit_amount')
def update_expense_tracking_items(tracking_id):
    """Update expense tracking items (manager can edit amounts before approval)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json() or {}
        items = data.get('items', [])
        
        if not items:
            return jsonify({'success': False, 'error': 'No items provided'}), 400
        
        conn, cur = connection()
        
        # Check tracking status - can only edit if pending
        cur.execute("SELECT status FROM expense_tracking WHERE id = %s", (tracking_id,))
        tracking = cur.fetchone()
        
        if not tracking:
            return jsonify({'success': False, 'error': 'Tracking not found'}), 404
        
        if tracking['status'] != 'pending':
            return jsonify({'success': False, 'error': 'Can only edit items when status is pending'}), 400
        
        # Update each item
        for item in items:
            item_id = item.get('id')
            new_amount = item.get('amount')
            new_description = item.get('description')
            
            if item_id and new_amount is not None:
                cur.execute("""
                    UPDATE expense_tracking_items 
                    SET amount = %s, item_description = COALESCE(%s, item_description)
                    WHERE id = %s AND tracking_id = %s
                """, (float(new_amount), new_description, item_id, tracking_id))
        
        # Recalculate total amount
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total FROM expense_tracking_items WHERE tracking_id = %s
        """, (tracking_id,))
        new_total = cur.fetchone()['total']
        
        cur.execute("""
            UPDATE expense_tracking SET total_amount = %s WHERE id = %s
        """, (new_total, tracking_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Items updated successfully',
            'new_total': float(new_total)
        })
    except Exception as e:
        print(f"Error updating expense tracking items: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# END EXPENSE TRACKING MODULE
# ============================================================================


# ============================================================================
# END FINANCE MODULE
# ============================================================================

if __name__== '__main__':
    # Run database migration on startup
    run_sales_request_migration()
    
    # Initialize default templates if missing
    print("\n=== Checking Default Templates ===")
    template_init_result = initialize_default_templates()
    if template_init_result.get('success'):
        print(f"✓ Templates ready: {template_init_result.get('templates_added', 0)} added, {template_init_result.get('templates_skipped', 0)} existed")
    else:
        print(f"⚠ Warning: Template initialization had issues: {template_init_result.get('error', 'Unknown error')}")
    
    app.jinja_env.auto_reload = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host='0.0.0.0', port=4008, debug=True, ssl_context=("cert.pem", "key.pem"))
    ##Initialize Firebase
    #initialize_firebase()
