from flask import Flask, request, jsonify
import datetime
import os
import hashlib # تأكد من وجود هذا
import uuid     # <--- أضف هذا الاستيراد الضروري!


app = Flask(__name__)

registered_devices = {} # سيعاد تعيينه مع كل إعادة تشغيل في الطبقة المجانية
next_server_client_id_counter = 1001 # لإنشاء client_id فريد من الخادم







# --- <<< بداية الكود الجديد لنقطة نهاية معلومات التحديث >>> ---
UPDATE_DATA = {
  "latest_version": "0.1.1",  # افترض أن هذا هو أحدث إصدار لديك حاليًا
  "release_date": "2025-06-20",
  "download_url": "https://github.com/YOUR_USERNAME/YOUR_REPO/releases/latest/download/EsekanLauncher_0.1.1.zip", # مثال لرابط تحميل
  "changelog_url": "https://github.com/YOUR_USERNAME/YOUR_REPO/blob/main/CHANGELOG.md#0.1.1", # مثال لرابط سجل التغييرات
  "notes": "تم إصلاح المشكلة X وإضافة الميزة Y في الإصدار 0.1.1.",
  "force_update_older_than": "0.0.5" # (اختياري)
}

@app.route('/api/v1/app/updateinfo', methods=['GET'])
def get_update_info():
    print(f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] --- Received /updateinfo request ---")
    # يمكنك هنا إضافة منطق أكثر تعقيدًا إذا أردت،
    # مثل قراءة هذه البيانات من ملف JSON منفصل على الخادم،
    # أو حتى التحقق من هيدر معين من العميل (مثل اسم البرنامج) إذا كان الخادم سيخدم عدة تطبيقات.
    # حاليًا، سنرجع البيانات الثابتة المحددة أعلاه.
    return jsonify(UPDATE_DATA), 200
# --- <<< نهاية الكود الجديد لنقطة نهاية معلومات التحديث >>> ---









# =============================================================================
#  >>> أضف هذه الدالة هنا <<<
# =============================================================================
def calculate_server_hash(device_serial, utc_timestamp_salt, machine_guid):
    """
    Server-side function to recalculate the hash.
    MUST match the client's logic and salt (timestamp) format.
    Format: device_serial{utc_timestamp_salt}machine_guid
    """
    if not all([device_serial, utc_timestamp_salt, machine_guid]):
        print("SERVER_HASH_CALC_ERROR: Missing components for server-side hash calculation.")
        return None # أو ارمي استثناء
    
    string_to_hash = f"{device_serial}{utc_timestamp_salt}{machine_guid}"
    encoded_string = string_to_hash.encode('utf-8')
    sha256_hasher = hashlib.sha256()
    sha256_hasher.update(encoded_string)
    return sha256_hasher.hexdigest()
# =============================================================================
#  >>> نهاية الدالة المضافة <<<
# =============================================================================



SERVER_STATIC_SALT = "esekan"




# =============================================================================
#  دوال حساب الهاش على الخادم
# =============================================================================
def calculate_hash_step1_on_server(device_serial, salt_time, machine_guid):
    if not all([device_serial, salt_time, machine_guid]):
        print(f"SERVER_HASH1_CALC_ERROR: Missing components. Serial: {bool(device_serial)}, Salt: {bool(salt_time)}, GUID: {bool(machine_guid)}")
        return None
    string_to_hash = f"{device_serial}{salt_time}{machine_guid}"
    return hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()

def calculate_hash_step2_on_server(sys_manufacturer, static_salt, sys_product_name, hash_from_step1):
    if not all([sys_manufacturer, static_salt, sys_product_name, hash_from_step1]):
        print(f"SERVER_HASH2_CALC_ERROR: Missing components. Manuf: {bool(sys_manufacturer)}, Salt: {bool(static_salt)}, Prod: {bool(sys_product_name)}, Hash1: {bool(hash_from_step1)}")
        return None
    string_to_hash = f"{sys_manufacturer}{static_salt}{sys_product_name}{hash_from_step1}"
    return hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()
# =============================================================================

@app.route('/api/v1/device/register', methods=['POST'])
def comprehensive_register_device_v3(): # اسم وصفي للدالة
    current_time_utc = datetime.datetime.now(datetime.timezone.utc)
    print(f"\n[{current_time_utc.isoformat()}] --- Received V3 COMPREHENSIVE /register request ---")
    
    try:
        data = request.get_json()
        if not data:
            print("REGISTER_ERROR_V3: Request body is not JSON or is empty.")
            return jsonify({"error": "Invalid request. JSON body expected."}), 400
        
        data_str_for_log = str(data)
        print(f"REGISTER_REQUEST_JSON_V3 (first 500 chars): {data_str_for_log[:500]}{'...' if len(data_str_for_log) > 500 else ''}")

        # استخراج البيانات من الكلاينت
        client_serial_raw = data.get('device_serial_raw')
        client_guid_raw = data.get('machine_guid_raw')
        client_timestamp_salt = data.get('timestamp_salt_used')
        client_hash_step1 = data.get('calculated_fingerprint_hash_step1')
        client_hash_step2_verification = data.get('verification_hash_step2')
        
        full_report = data.get('full_system_report', {})
        # استخراج SystemManufacturer و SystemProductName من التقرير الشامل
        # تأكد أن هذه المفاتيح هي التي يرسلها الكلاينت
        system_manufacturer_from_report = full_report.get("Hardware", {}).get("SystemManufacturer", "N/A_MANUF_RPT").strip()
        system_product_name_from_report = full_report.get("Hardware", {}).get("SystemModel", "N/A_PROD_RPT").strip()
        
        device_name_from_payload = data.get('device_name_provided', 
                                     full_report.get("SystemIdentity", {}).get("Hostname", "UnknownDevice"))

        # التحقق من وجود جميع المكونات الضرورية
        critical_components = {
            "device_serial_raw": client_serial_raw, "machine_guid_raw": client_guid_raw,
            "timestamp_salt_used": client_timestamp_salt, "calculated_fingerprint_hash_step1": client_hash_step1,
            "verification_hash_step2": client_hash_step2_verification,
            "system_manufacturer_from_report": system_manufacturer_from_report,
            "system_product_name_from_report": system_product_name_from_report
        }
        missing_fields = [k for k, v in critical_components.items() if not v or (isinstance(v, str) and v.startswith("N/A_"))]

        if missing_fields:
            error_message = f"Missing or invalid critical components for V3 registration. Check: {', '.join(missing_fields)}"
            print(f"REGISTER_ERROR_V3: {error_message}")
            return jsonify({"error": error_message}), 400

        # --- الخطوة 1: التحقق من الهاش الأول ---
        server_calculated_hash_step1 = calculate_hash_step1_on_server(
            client_serial_raw,
            client_timestamp_salt,
            client_guid_raw
        )

        if server_calculated_hash_step1 is None: # فشل في الحساب
             print("REGISTER_ERROR_V3: Server-side hash1 calculation failed (missing components for calc func).")
             return jsonify({"error": "Server error during hash1 calculation."}), 500

        if server_calculated_hash_step1 != client_hash_step1:
            print(f"HASH1_MISMATCH_V3: ServerCalc={server_calculated_hash_step1}, ClientSent={client_hash_step1}")
            return jsonify({"error": "Initial fingerprint (step 1) verification failed.", "status": "hash1_mismatch"}), 401
        print("Initial fingerprint (step 1) VERIFIED successfully.")

        # --- الخطوة 2: التحقق من الهاش الثاني ---
        server_calculated_hash_step2 = calculate_hash_step2_on_server(
            system_manufacturer_from_report,
            SERVER_STATIC_SALT, # الملح الثابت الخاص بالخادم
            system_product_name_from_report,
            client_hash_step1 # استخدم الهاش الأول (المُتحقق منه) كجزء من الهاش الثاني
        )

        if server_calculated_hash_step2 is None: # فشل في الحساب
            print("REGISTER_ERROR_V3: Server-side hash2 calculation failed (missing components for calc func).")
            return jsonify({"error": "Server error during hash2 calculation."}), 500

        if server_calculated_hash_step2 != client_hash_step2_verification:
            print(f"HASH2_MISMATCH_V3: ServerCalc={server_calculated_hash_step2}, ClientSent={client_hash_step2_verification}")
            print(f"  Debug HASH2 Inputs: Manuf='{system_manufacturer_from_report}', StaticSalt='{SERVER_STATIC_SALT}', Prod='{system_product_name_from_report}', Hash1='{client_hash_step1}'")
            return jsonify({"error": "Secondary verification hash (step 2) failed.", "status": "hash2_mismatch"}), 401
        print("Secondary verification hash (step 2) VERIFIED successfully.")

        # --- (اختياري) الخطوة 3: شغل "الخوارزمية المعينة" على full_report ---
        print("Custom algorithm/policy check PASSED (or skipped for now).")

        # --- الخطوة 4: تم التحقق من كل شيء، قم بالتسجيل وتوليد الترخيص ---
        unique_hw_identifier_for_server_db = f"{client_serial_raw}_{client_guid_raw}"
        
        final_client_id_to_return = None
        generated_license_key = None
        device_already_existed = False

        for s_id, dev_info in registered_devices.items():
            if dev_info.get('unique_hw_id') == unique_hw_identifier_for_server_db:
                final_client_id_to_return = s_id
                generated_license_key = dev_info.get('license_key', f"EXISTING_LIC_{s_id}_{os.urandom(4).hex().upper()}")
                dev_info['last_full_registration_utc'] = current_time_utc.isoformat()
                dev_info['device_name'] = device_name_from_payload
                device_already_existed = True
                message = "Device re-validated and license confirmed (V3)."
                break
        
        if not device_already_existed:
            final_client_id_to_return = str(uuid.uuid4())
            generated_license_key = f"ESK_LIC_V3_{final_client_id_to_return[:8].upper()}_{os.urandom(6).hex().upper()}"
            
            registered_devices[final_client_id_to_return] = {
                'unique_hw_id': unique_hw_identifier_for_server_db,
                'device_name': device_name_from_payload,
                'license_key': generated_license_key,
                'registration_utc': current_time_utc.isoformat(),
            }
            message = "Device registered (V3) and license generated successfully!"
        
        print(f"SUCCESS_V3: Device '{unique_hw_identifier_for_server_db}'. ClientID: {final_client_id_to_return}, License: {generated_license_key}")

        return jsonify({
            "status": "success",
            "message": message,
            "client_id": final_client_id_to_return,
            "license_key": generated_license_key
        }), 200

    except Exception as e:
        print(f"REGISTER_EXCEPTION_V3: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Internal server error during V3 registration", "details": str(e)}), 500

@app.route('/api/v1/device/heartbeat', methods=['POST'])
def heartbeat():
    current_time_utc = datetime.datetime.now(datetime.timezone.utc)
    print(f"\n[{current_time_utc.isoformat()}] --- Received /heartbeat request ---")
    # ... (الكود المتبقي كما هو، ولكن استخدم current_time_utc بدلاً من datetime.datetime.utcnow()) ...
    client_id_from_header = request.headers.get('X-Device-ID')
    if not client_id_from_header: # ... (return error) ...
        return jsonify({"error": "X-Device-ID header is required"}), 400

    if client_id_from_header in registered_devices:
        registered_devices[client_id_from_header]['last_heartbeat_utc'] = current_time_utc.isoformat()
        message = "Heartbeat acknowledged."
        print(f"HEARTBEAT_SUCCESS: For ClientID: {client_id_from_header}")
        return jsonify({"message": message, "status": "success", "data": {"server_time": current_time_utc.isoformat()}}), 200
    else:
        message = "Device not recognized (ClientID unknown)."
        print(f"HEARTBEAT_REJECTED: Unknown ClientID: {client_id_from_header}")
        return jsonify({"error": message, "status": "unauthorized"}), 401


@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "Esekan Mock Server (Comprehensive Register) is UP!", 
                    "time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5500))
    print(f"Starting server on host 0.0.0.0, port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True) # debug=True جيد للاختبار المحلي