from flask import Flask, request, jsonify
import datetime
import os
import hashlib # تأكد من وجود هذا
import uuid     # <--- أضف هذا الاستيراد الضروري!
# test_mock_server.py
import json
import os

app = Flask(__name__)



SERVER_STATIC_SALT = "77e78b7b-af09-491e-96e7-a6209e689ba6"




registered_devices = {} # سيعاد تعيينه مع كل إعادة تشغيل في الطبقة المجانية
next_server_client_id_counter = 1001 # لإنشاء client_id فريد من الخادم



# --- هذا هو التعريف الصحيح الذي يجب الإبقاء عليه ---
DEVICES_FILE = 'registered_devices_mock.json'
registered_devices = {} # سيتم ملؤه بواسطة load_devices()
# --- نهاية التعريف الصحيح ---



def load_devices():
    global registered_devices # ضروري لتعديل المتغير العام
    if os.path.exists(DEVICES_FILE):
        try:
            with open(DEVICES_FILE, 'r') as f:
                # يجب التأكد من أن registered_devices هنا هو المتغير العام
                data_from_file = json.load(f)
                if isinstance(data_from_file, dict): # تحقق أن ما تم تحميله هو قاموس
                    registered_devices = data_from_file
                    print(f"Loaded {len(registered_devices)} devices from {DEVICES_FILE}")
                else:
                    print(f"Data in {DEVICES_FILE} is not a dictionary. Starting fresh.")
                    registered_devices = {}
        except json.JSONDecodeError:
            print(f"Error decoding JSON from {DEVICES_FILE}. Starting fresh.")
            registered_devices = {}
        except Exception as e:
            print(f"Unexpected error loading devices from {DEVICES_FILE}: {e}. Starting fresh.")
            registered_devices = {}
    else:
        print(f"{DEVICES_FILE} not found. Starting fresh.")
        registered_devices = {}

def save_devices():
    global registered_devices # ليس ضروريًا إذا كنت تقرأ فقط، ولكنه لا يضر
    try:
        with open(DEVICES_FILE, 'w') as f:
            json.dump(registered_devices, f, indent=4)
        print(f"Saved {len(registered_devices)} devices to {DEVICES_FILE}")
    except Exception as e:
        print(f"Error saving devices to {DEVICES_FILE}: {e}")


# استدعي load_devices() عند بدء تشغيل الخادم (في بداية تحميل الوحدة)
load_devices()






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




"""

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
            
            is_this_device_premium = False # أو True بناءً على منطق ما
            registered_devices[final_client_id_to_return] = {
                'raw_serial': client_serial_raw,     # <--- !!!!! تأكد من هذا السطر !!!!!
                'raw_guid': client_guid_raw,         # <--- !!!!! وهذا السطر !!!!!
                'unique_hw_id': unique_hw_identifier_for_server_db,
                'device_name': device_name_from_payload,
                'license_key': generated_license_key,
                'registration_utc': current_time_utc.isoformat(),
                'last_heartbeat_utc': current_time_utc.isoformat(), # جيد لإضافة هذا
                'last_routine_check_utc': current_time_utc.isoformat(), # ج
                'is_premium_user': is_this_device_premium, # <--- !!!! تخزين حالة Premium !!!!
                'system_model': system_product_name_from_report
            }
            message = "Device registered (V3) and license generated successfully!"
        else: # إذا كان الجهاز موجودًا، ربما لا تغير حالته premium إلا إذا كان هناك منطق لذلك
            if 'is_premium_user' not in registered_devices[final_client_id_to_return]:
                registered_devices[final_client_id_to_return]['is_premium_user'] = False # قيمة افتراضية
            
            
        
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

"""

# افترض أن الاستيرادات التالية موجودة في أعلى ملف test_mock_server.py
# import datetime
# import os
# import hashlib
# import uuid
# import json
# from flask import Flask, request, jsonify
# registered_devices = {} # أو يتم تحميلها من ملف
# SERVER_STATIC_SALT = "YourSalt" # يجب أن يكون معرفًا
# def load_devices(): ...
# def save_devices(): ...
# def calculate_hash_step1_on_server(...): ...
# def calculate_hash_step2_on_server(...): ...

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
        client_guid_raw = data.get('machine_guid_raw') # افترض أنك لا تزال ترسله للتوافق مع unique_hw_identifier
        client_timestamp_salt = data.get('timestamp_salt_used')
        client_hash_step1 = data.get('calculated_fingerprint_hash_step1')
        client_hash_step2_verification = data.get('verification_hash_step2')
        
        full_report = data.get('full_system_report', {})
        system_manufacturer_from_report = full_report.get("Hardware", {}).get("SystemManufacturer", "N/A_MANUF_RPT").strip()
        # هذا هو SystemModel الذي نهتم به
        actual_system_model_from_report = full_report.get("Hardware", {}).get("SystemModel", "N/A_PROD_RPT").strip() 
        
        device_name_from_payload = data.get('device_name_provided', 
                                     full_report.get("SystemIdentity", {}).get("Hostname", "UnknownDevice"))
        
        # التحقق من وجود جميع المكونات الضرورية
        critical_components = {
            "device_serial_raw": client_serial_raw, 
            "machine_guid_raw": client_guid_raw, # أبقه إذا كان unique_hw_identifier يعتمد عليه
            "timestamp_salt_used": client_timestamp_salt, 
            "calculated_fingerprint_hash_step1": client_hash_step1,
            "verification_hash_step2": client_hash_step2_verification,
            "system_manufacturer_from_report": system_manufacturer_from_report,
            "actual_system_model_from_report": actual_system_model_from_report # استخدم الاسم الجديد هنا
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
            client_guid_raw # افترض أن هذه الدالة لا تزال تتوقع GUID
        )

        if server_calculated_hash_step1 is None: 
             print("REGISTER_ERROR_V3: Server-side hash1 calculation failed (missing components for calc func).")
             return jsonify({"error": "Server error during hash1 calculation."}), 500

        if server_calculated_hash_step1 != client_hash_step1:
            print(f"HASH1_MISMATCH_V3: ServerCalc={server_calculated_hash_step1}, ClientSent={client_hash_step1}")
            return jsonify({"error": "Initial fingerprint (step 1) verification failed.", "status": "hash1_mismatch"}), 401
        print("Initial fingerprint (step 1) VERIFIED successfully.")

        # --- الخطوة 2: التحقق من الهاش الثاني ---
        server_calculated_hash_step2 = calculate_hash_step2_on_server(
            system_manufacturer_from_report,
            SERVER_STATIC_SALT, 
            actual_system_model_from_report, # استخدم actual_system_model_from_report هنا
            client_hash_step1 
        )

        if server_calculated_hash_step2 is None: 
            print("REGISTER_ERROR_V3: Server-side hash2 calculation failed (missing components for calc func).")
            return jsonify({"error": "Server error during hash2 calculation."}), 500

        if server_calculated_hash_step2 != client_hash_step2_verification:
            print(f"HASH2_MISMATCH_V3: ServerCalc={server_calculated_hash_step2}, ClientSent={client_hash_step2_verification}")
            print(f"  Debug HASH2 Inputs: Manuf='{system_manufacturer_from_report}', StaticSalt='{SERVER_STATIC_SALT}', Prod='{actual_system_model_from_report}', Hash1='{client_hash_step1}'")
            return jsonify({"error": "Secondary verification hash (step 2) failed.", "status": "hash2_mismatch"}), 401
        print("Secondary verification hash (step 2) VERIFIED successfully.")

        # --- (اختياري) الخطوة 3: شغل "الخوارزمية المعينة" على full_report ---
        print("Custom algorithm/policy check PASSED (or skipped for now).")

        # --- الخطوة 4: تم التحقق من كل شيء، قم بالتسجيل وتوليد الترخيص ---
        unique_hw_identifier_for_server_db = f"{client_serial_raw}_{client_guid_raw}" # افترض أنك لا تزال تستخدم GUID هنا للمعرف الفريد
        
        final_client_id_to_return = None
        generated_license_key = None
        device_already_existed = False
        device_entry_updated = False # لتتبع ما إذا كنا بحاجة للحفظ

        for s_id, dev_info in registered_devices.items():
            if dev_info.get('unique_hw_id') == unique_hw_identifier_for_server_db:
                final_client_id_to_return = s_id
                generated_license_key = dev_info.get('license_key', f"EXISTING_LIC_{s_id}_{os.urandom(4).hex().upper()}")
                
                # تحديث المعلومات الحالية إذا تغيرت
                if dev_info.get('device_name') != device_name_from_payload:
                    dev_info['device_name'] = device_name_from_payload
                    device_entry_updated = True
                
                # تحديث/إضافة system_model
                if dev_info.get('system_model') != actual_system_model_from_report:
                    dev_info['system_model'] = actual_system_model_from_report
                    device_entry_updated = True
                    print(f"  Updated system_model for existing device {s_id} to '{actual_system_model_from_report}'")
                
                # تحديث الطابع الزمني دائمًا عند إعادة التحقق
                dev_info['last_full_registration_utc'] = current_time_utc.isoformat()
                device_entry_updated = True 
                
                device_already_existed = True
                message = "Device re-validated and license confirmed (V3)."
                break
        
        if not device_already_existed:
            final_client_id_to_return = str(uuid.uuid4())
            generated_license_key = f"ESK_LIC_V3_{final_client_id_to_return[:8].upper()}_{os.urandom(6).hex().upper()}"
            
            is_this_device_premium = False 
            registered_devices[final_client_id_to_return] = {
                'raw_serial': client_serial_raw,
                'raw_guid': client_guid_raw, # إذا كنت لا تزال تخزنه
                'unique_hw_id': unique_hw_identifier_for_server_db,
                'device_name': device_name_from_payload,
                'license_key': generated_license_key,
                'registration_utc': current_time_utc.isoformat(),
                'last_heartbeat_utc': current_time_utc.isoformat(),
                'last_routine_check_utc': current_time_utc.isoformat(),
                'is_premium_user': is_this_device_premium,
                'system_model': actual_system_model_from_report # تخزين موديل النظام عند الإنشاء الجديد
            }
            device_entry_updated = True 
            message = "Device registered (V3) and license generated successfully!"
        else: # إذا كان الجهاز موجودًا، تأكد من أن الحقول الإضافية مثل is_premium_user موجودة
            if 'is_premium_user' not in registered_devices[final_client_id_to_return]:
                registered_devices[final_client_id_to_return]['is_premium_user'] = False 
                device_entry_updated = True
            # تأكد أيضًا من وجود system_model إذا كان الجهاز قديمًا ولم يكن به هذا الحقل
            if 'system_model' not in registered_devices[final_client_id_to_return]:
                registered_devices[final_client_id_to_return]['system_model'] = actual_system_model_from_report
                device_entry_updated = True
                print(f"  Added missing system_model for existing device {final_client_id_to_return} to '{actual_system_model_from_report}'")


        if device_entry_updated: 
            save_devices()
        
        print(f"SUCCESS_V3: Device '{unique_hw_identifier_for_server_db}'. ClientID: {final_client_id_to_return}, License: {generated_license_key}")

        return jsonify({
            "status": "success",
            "message": message,
            "client_id": final_client_id_to_return,
            "license_key": generated_license_key
        }), 200

    except Exception as e:
        print(f"REGISTER_EXCEPTION_V3: {e}")
        import traceback # تأكد من استيراد traceback إذا لم يكن مستوردًا بالفعل
        print(traceback.format_exc())
        return jsonify({"error": "Internal server error during V3 registration", "details": str(e)}), 500


@app.route('/api/v1/device/heartbeat', methods=['POST'])
def heartbeat(): # هذه هي النبضة "الخفيفة" الأصلية
    current_time_utc = datetime.datetime.now(datetime.timezone.utc)
    print(f"\n[{current_time_utc.isoformat()}] --- Received ORIGINAL /heartbeat request ---")
    
    client_id_from_header = request.headers.get('X-Device-ID')
    if not client_id_from_header:
        print("ORIGINAL_HEARTBEAT_ERROR: X-Device-ID header is required.")
        return jsonify({"error": "X-Device-ID header is required"}), 400

    if client_id_from_header in registered_devices:
        # تحديث وقت آخر نبضة قلب لهذه النبضة الخفيفة أيضًا
        registered_devices[client_id_from_header]['last_heartbeat_utc'] = current_time_utc.isoformat()
        save_devices() # <--- مهم: احفظ التغيير
        
        message = "Original Heartbeat acknowledged."
        print(f"ORIGINAL_HEARTBEAT_SUCCESS: For ClientID: {client_id_from_header}")
        
        notifications_for_client = [] # يمكنك إضافة إشعارات هنا إذا أردت
        # مثال:
        # if registered_devices[client_id_from_header].get("new_message_flag"):
        #     notifications_for_client.append({"id": "msg123", "message": "You have a new server message!"})
        #     registered_devices[client_id_from_header]["new_message_flag"] = False # Clear flag
        #     save_devices()

        return jsonify({
            "message": message, 
            "status": "success", 
            "data": {
                "server_time": current_time_utc.isoformat(),
                "notifications": notifications_for_client 
            }
        }), 200
    else:
        message = "Device not recognized (ClientID unknown for original heartbeat)."
        print(f"ORIGINAL_HEARTBEAT_REJECTED: Unknown ClientID: {client_id_from_header}")
        return jsonify({"error": message, "status": "unauthorized"}), 401



# تم تغيير اسم الدالة ليتناسب مع routinecheck
def calculate_device_check_hash_on_server(stored_serial, timestamp_salt_from_client, client_id):
    if not all([stored_serial, timestamp_salt_from_client, client_id]):
        print("SERVER_ROUTINE_CHECK_HASH_Error: Missing components.")
        return None
    string_to_hash = f"{stored_serial}{timestamp_salt_from_client}{client_id}"
    return hashlib.sha256(string_to_hash.encode('utf-8')).hexdigest()


@app.route('/api/v1/device/routinecheck', methods=['POST'])
def routine_check_endpoint(): # تم تغيير اسم الدالة ليكون أوضح
    current_time_utc = datetime.datetime.now(datetime.timezone.utc)
    print(f"\n[{current_time_utc.isoformat()}] --- Received /routinecheck request (with hash check) ---")
    
    client_id_from_header = request.headers.get('X-Device-ID')
    if not client_id_from_header:
        return jsonify({"error": "X-Device-ID header is required"}), 400

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request. JSON body expected."}), 400
        
        client_timestamp_salt = data.get("timestamp_salt")
        client_check_hash = data.get("check_hash") # اسم مقترح للهاش الخاص بالـ routinecheck

        if not client_timestamp_salt or not client_check_hash:
            return jsonify({"error": "'timestamp_salt' and 'check_hash' are required in payload"}), 400
    except Exception as e:
        return jsonify({"error": f"Invalid JSON payload: {e}"}), 400

    if client_id_from_header in registered_devices:
        device_info = registered_devices[client_id_from_header]
        stored_raw_serial = device_info.get('raw_serial')

        if not stored_raw_serial:
            print(f"ROUTINE_CHECK_ERROR: No raw_serial stored for ClientID {client_id_from_header}")
            return jsonify({"error": "Server configuration error for this device (missing serial)."}), 500

        server_calculated_hash = calculate_device_check_hash_on_server( # استخدام الدالة بالاسم الجديد
            stored_raw_serial,
            client_timestamp_salt,
            client_id_from_header
        )

        if server_calculated_hash and server_calculated_hash == client_check_hash:
            # يمكنك تحديث طابع زمني مختلف هنا إذا أردت، مثل 'last_routine_check_utc'
            device_info['last_routine_check_utc'] = current_time_utc.isoformat() 
            # أو يمكنك تحديث 'last_heartbeat_utc' أيضًا إذا اعتبرت هذا نوعًا من الـ heartbeat
            device_info['last_heartbeat_utc'] = current_time_utc.isoformat() 
            save_devices()
            message = "Routine check successful (hash verified)."
            print(f"ROUTINE_CHECK_SUCCESS: For ClientID: {client_id_from_header}")
            return jsonify({"message": message, "status": "success", "data": {"server_time": current_time_utc.isoformat()}}), 200
        else:
            message = "Routine check verification failed (hash mismatch)."
            print(f"ROUTINE_CHECK_REJECTED (HASH_MISMATCH): ClientID: {client_id_from_header}. ServerCalc: {server_calculated_hash}, ClientSent: {client_check_hash}")
            return jsonify({"error": message, "status": "hash_mismatch"}), 403
    else:
        message = "Device not recognized (ClientID unknown for routine check)."
        print(f"ROUTINE_CHECK_REJECTED: Unknown ClientID: {client_id_from_header}")
        return jsonify({"error": message, "status": "unauthorized"}), 401



@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "Esekan Mock Server (Comprehensive Register) is UP!", 
                    "time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}), 200


class DeviceRoutineChecker:
    def __init__(self, registered_devices_dict):
        self.registered_devices = registered_devices_dict # هذا لا يزال مفيدًا للوصول إلى معلومات الجهاز إذا لزم الأمر


    def _get_device_info(self, client_id): # سيبقى مفيدًا
        return self.registered_devices.get(client_id)

    # --- دوال تحقق بسيطة كأمثلة ---
    def check_constant_value_A(self, client_id, client_data):
        """
        العميل يرسل قيمة، الخادم يتأكد أنها تطابق قيمة ثابتة A.
        client_data: يجب أن يكون قاموسًا يحتوي على المفتاح 'value_to_check'.
        """
        print(f"SERVER: check_constant_value_A called for ClientID: {client_id} with data: {client_data}")
        expected_value = "5344" # القيمة الثابتة A
        received_value = client_data.get("value_to_check")

        if received_value == expected_value:
            return {"success": True, "message": f"Check A successful. Client sent '{received_value}'."}
        else:
            return {"success": False, "error": f"Check A failed. Expected '{expected_value}', got '{received_value}'.", "status_code": 400}


    def check_constant_value_B(self, client_id, client_data):
        """
        العميل يرسل قيمة، الخادم يتأكد أنها تطابق قيمة ثابتة B.
        """
        print(f"SERVER: check_constant_value_B called for ClientID: {client_id} with data: {client_data}")
        expected_value = "2342" # القيمة الثابتة B
        received_value = client_data.get("value_to_check")

        if received_value == expected_value:
            return {"success": True, "message": f"Check B successful. Client sent '{received_value}'."}
        else:
            return {"success": False, "error": f"Check B failed. Expected '{expected_value}', got '{received_value}'.", "status_code": 400}


    def check_if_device_is_premium(self, client_id, client_data):
        """
        مثال: يتحقق مما إذا كان الجهاز لديه علامة "premium" في معلوماته المخزنة.
        client_data: قد لا يكون ضروريًا لهذا التحقق، أو يمكن أن يحتوي على شيء إضافي.
        """
        print(f"SERVER: check_if_device_is_premium called for ClientID: {client_id} with data: {client_data}")
        device_info = self._get_device_info(client_id)
        if not device_info:
            return {"success": False, "error": "Device not recognized.", "status_code": 401}

        if device_info.get("is_premium_user", False): # افترض أنك تخزن هذا عند التسجيل أو من خلال واجهة إدارية
            return {"success": True, "message": "Device is confirmed as premium."}
        else:
            return {"success": False, "error": "Device is not marked as premium.", "status_code": 403}


    def check_system_model_with_salt(self, client_id, client_data):
        """
        يستقبل SystemModel مُملح من العميل،
        ويقارنه بـ SystemModel الخاص بالجهاز (من بيانات التسجيل) بعد تمليحه بملح الخادم.
        client_data: يجب أن يحتوي على "salted_system_model_from_client".
        """
        print(f"SERVER: check_system_model_with_salt called for ClientID: {client_id} with data: {client_data}")
        device_info = self._get_device_info(client_id)
        if not device_info:
            return {"success": False, "error": "Device not recognized.", "status_code": 401}

        # نحتاج إلى SystemModel المخزن للجهاز.
        # هذا يعتمد على كيفية تخزين full_system_report عند التسجيل.
        # لنفترض أننا سنحصل عليه من 'full_system_report' المخزن (إذا كنت تخزنه)
        # أو من حقل مخصص مثل 'stored_system_model'.
        # حاليًا، كود التسجيل يرسل full_system_report ولكن لا يخزنه كله.
        # سنحتاج لتعديل التسجيل ليخزن SystemModel أو نعتمد على أن الكلاينت سيرسله دائمًا.

        # الطريقة الأبسط حاليًا هي افتراض أننا نحصل عليه من `full_system_report` الذي يرسله الكلاينت
        # عند التسجيل، ويجب أن يكون قد تم تخزينه في `device_info`.
        # إذا لم يكن مخزنًا، ستحتاج لتعديل منطق التسجيل.

        # مثال إذا كان مخزنًا مباشرة في device_info (تحت مفتاح معين مثل 'system_model'):
        # stored_system_model = device_info.get('system_model')

        # للحصول عليه من `full_system_report` الذي *يجب* أن يكون الكلاينت قد أرسله عند التسجيل
        # وكان يجب على الخادم تخزينه، أو جزء منه.
        # نظرًا لأن `comprehensive_register_device_v3` يستخرج system_manufacturer_from_report
        # و system_product_name_from_report من full_report، يمكننا افتراض أننا
        # سنحتاج لتخزين SystemModel أيضًا عند التسجيل إذا أردنا استخدامه هنا.

        # تعديل مؤقت: لنفترض أن `client_data` يمكن أن يحتوي على `system_model_from_client_raw` كحل بديل
        # إذا لم يكن مخزنًا، ولكن هذا ليس مثاليًا للأمان.
        # الأفضل هو تخزينه عند التسجيل.

        # === الحل الأفضل: افترض أن SystemModel مخزن عند التسجيل ===
        # عدّل دالة comprehensive_register_device_v3 لتخزن 'system_model'
        # registered_devices[final_client_id_to_return]['system_model'] = system_product_name_from_report 
        # (أو system_model_from_report إذا كان لديك هذا المفتاح)

        # الآن، افترض أنه مخزن:
        stored_system_model = device_info.get('system_model') # أو 'product_name' أو المفتاح الصحيح
        if not stored_system_model:
            # إذا لم يكن `system_model` مخزنًا، جرب الحصول عليه من `client_data` (كحل مؤقت إذا كان الكلاينت يرسله)
            # هذا يتطلب أن يرسل الكلاينت `system_model` خام أيضًا في `check_payload`
            # وهو ليس ما فعلناه في الكلاينت. لذا، هذا سيفشل حاليًا.
            # **يجب تعديل التسجيل ليخزن SystemModel**
            print(f"SERVER_ERROR: 'system_model' not found in stored device_info for ClientID {client_id}.")
            return {"success": False, "error": "Server configuration error: SystemModel not stored for this device.", "status_code": 500}

        salted_system_model_from_client = client_data.get("salted_system_model_from_client")
        if not salted_system_model_from_client:
            return {"success": False, "error": "Missing 'salted_system_model_from_client' in payload.", "status_code": 400}

        # التأكد من أن SERVER_STATIC_SALT مُعرف
        if not SERVER_STATIC_SALT: # SERVER_STATIC_SALT يجب أن يكون مُعرفًا في أعلى الملف
             print("SERVER_ERROR: SERVER_STATIC_SALT is not defined on the server!")
             return {"success": False, "error": "Server-side static salt not configured.", "status_code": 500}

        server_calculated_salted_model = f"{stored_system_model}{SERVER_STATIC_SALT}"
        print(f"  Server calculated: '{server_calculated_salted_model}' (StoredModel: '{stored_system_model}', Salt: '{SERVER_STATIC_SALT}')")
        print(f"  Client sent: '{salted_system_model_from_client}'")


        if server_calculated_salted_model == salted_system_model_from_client:
            return {"success": True, "message": "System Model with Salt check successful."}
        else:
            return {"success": False, "error": "System Model with Salt check failed (mismatch).", "status_code": 403}  

    # يمكنك إضافة المزيد من دوال التحقق هنا لاحقًا.

# إنشاء نسخة من الكلاس
device_checker = DeviceRoutineChecker(registered_devices)

# --- نقطة النهاية الجديدة للتحقق المتعدد ---
@app.route('/api/v1/device/perform_check', methods=['POST'])
def perform_check_endpoint():
    current_time_utc = datetime.datetime.now(datetime.timezone.utc)
    print(f"\n[{current_time_utc.isoformat()}] --- Received /perform_check request ---")
    
    client_id = request.headers.get('X-Device-ID')
    if not client_id:
        return jsonify({"error": "X-Device-ID header is required"}), 400

    # أولاً، تحقق مما إذا كان الجهاز مسجلاً (ClientID موجود)
    if client_id not in registered_devices:
        print(f"PERFORM_CHECK_REJECTED: Unknown ClientID: {client_id}")
        return jsonify({"error": "Device not recognized (ClientID unknown).", "status": "unauthorized"}), 401

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request. JSON body expected."}), 400
        
        check_type = data.get("check_type")
        # 'check_payload' سيكون قاموسًا يحتوي على البيانات الخاصة بنوع التحقق
        check_payload = data.get("check_payload", {}) 

        if not check_type:
            return jsonify({"error": "'check_type' is required in payload."}), 400
        
        result = None
        if hasattr(device_checker, check_type) and callable(getattr(device_checker, check_type)):
            method_to_call = getattr(device_checker, check_type)
            print(f"PERFORM_CHECK: Calling method '{check_type}' for ClientID: {client_id}")
            result = method_to_call(client_id, check_payload) # تمرير الـ payload الخاص بالتحقق
        else:
            return jsonify({"error": f"Unknown or invalid check_type: {check_type}"}), 400

        if result and result.get("success"):
            # يمكنك تحديث طابع زمني عام لآخر فحص ناجح إذا أردت
            registered_devices[client_id]['last_generic_check_utc'] = current_time_utc.isoformat()
            save_devices() # احفظ إذا قمت بتحديث شيء
            return jsonify({"message": result["message"], "status": "success", "data": {"server_time": current_time_utc.isoformat()}}), 200
        else:
            error_msg = result.get("error", f"Check type '{check_type}' failed.") if result else f"Processing error for check_type '{check_type}'."
            status_code = result.get("status_code", 403) if result else 400 # 403 Forbidden إذا فشل التحقق، 400 إذا كان الطلب سيئًا
            print(f"PERFORM_CHECK_REJECTED: Type '{check_type}', ClientID: {client_id}. Reason: {error_msg}")
            return jsonify({"error": error_msg, "status": "failed"}), status_code

    except Exception as e:
        print(f"PERFORM_CHECK_EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Internal server error during perform_check", "details": str(e)}), 500





if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5500))
    print(f"Starting server on host 0.0.0.0, port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=True) # <--- أضف use_reloader=False) # debug=True جيد للاختبار المحلي