from flask import Flask, request, jsonify
import datetime
import os
import hashlib # تأكد من وجود هذا
import uuid     # <--- أضف هذا الاستيراد الضروري!


app = Flask(__name__)

registered_devices = {} # سيعاد تعيينه مع كل إعادة تشغيل في الطبقة المجانية
next_server_client_id_counter = 1001 # لإنشاء client_id فريد من الخادم

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


@app.route('/api/v1/device/register', methods=['POST'])
def comprehensive_register_device():
    # لم نعد بحاجة إلى global next_server_client_id_counter إذا استخدمنا UUID
    
    current_time_utc = datetime.datetime.now(datetime.timezone.utc) # استخدم هذا بدلاً من utcnow() المتكرر
    print(f"\n[{current_time_utc.isoformat()}] --- Received COMPREHENSIVE /register request ---")
    
    try:
        data = request.get_json()
        if not data:
            print("REGISTER_ERROR: Request body is not JSON or is empty.")
            return jsonify({"error": "Invalid request. JSON body expected."}), 400
        
        # اطبع جزءًا فقط إذا كان الـ payload كبيرًا جدًا لتجنب إغراق السجلات
        data_str_for_log = str(data)
        print(f"REGISTER_REQUEST_JSON (first 500 chars): {data_str_for_log[:500]}{'...' if len(data_str_for_log) > 500 else ''}")

        # استخراج البيانات من الكلاينت
        client_sent_hash = data.get('fingerprint_hash_calculated')
        client_sent_salt = data.get('timestamp_salt_used') # هذا هو التوقيت الذي استخدمه الكلاينت كملح
        
        full_report = data.get('full_system_report', {})
        # استخراج السيريال والـ GUID من التقرير الشامل
        device_serial_from_report = full_report.get("Hardware", {}).get("Motherboard", {}).get("SerialNumber", "N/A_SERIAL_RPT").strip()
        machine_guid_from_report = full_report.get("SystemIdentity", {}).get("MachineGUID_Registry", "N/A_GUID_RPT").strip()
        
        device_name_from_payload = data.get('device_name_provided', 
                                     full_report.get("SystemIdentity", {}).get("Hostname", "UnknownDevice"))

        # التحقق من وجود جميع المكونات الضرورية للتحقق من الهاش
        critical_components = {
            "fingerprint_hash_calculated": client_sent_hash,
            "timestamp_salt_used": client_sent_salt,
            "device_serial_from_report": device_serial_from_report,
            "machine_guid_from_report": machine_guid_from_report
        }
        missing_fields = [k for k, v in critical_components.items() if not v or v.startswith("N/A_")]

        if missing_fields:
            error_message = f"Missing critical components for hash verification or from report. Missing or invalid: {', '.join(missing_fields)}"
            print(f"REGISTER_ERROR: {error_message}")
            return jsonify({"error": error_message}), 400

        # 1. التحقق من صحة الهاش (إعادة حسابه على الخادم)
        hash_recalculated_by_server = calculate_server_hash(
            device_serial_from_report,
            client_sent_salt, # استخدم الملح (التوقيت) الذي أرسله الكلاينت
            machine_guid_from_report
        )

        if hash_recalculated_by_server is None: # فشل في الحساب بسبب مدخلات فارغة للدالة
            print("REGISTER_ERROR: Server-side hash calculation failed (likely missing components for calculate_server_hash).")
            return jsonify({"error": "Server error during hash calculation."}), 500
        
        print(f"Server-calculated hash: {hash_recalculated_by_server}")
        print(f"Client-provided hash:   {client_sent_hash}")

        # استخدام المقارنة المباشرة للسلاسل النصية (أبسط، ولخطر timing attack منخفض هنا)
        if hash_recalculated_by_server != client_sent_hash:
            print(f"HASH_MISMATCH: ServerCalc={hash_recalculated_by_server}, ClientSent={client_sent_hash}")
            return jsonify({"error": "Fingerprint hash verification failed. Hash mismatch.", "status": "hash_mismatch"}), 401
        
        print("Fingerprint hash VERIFIED successfully.")

        # 2. (اختياري) شغل "الخوارزمية المعينة" على full_report الآن بعد التحقق من الهاش
        # algorithm_passed = True # افترض أنها ناجحة مبدئيًا
        # if not algorithm_passes(full_report): # دالة افتراضية
        #     print("ALGORITHM_REJECT: Device does not meet registration criteria based on full report.")
        #     return jsonify({"error": "Device does not meet registration criteria."}), 403
        # print("Custom algorithm/policy check PASSED (or skipped).")


        # 3. إذا نجح كل شيء، قم بالتسجيل وتوليد الترخيص
        # استخدم مزيجًا من السيريال والـ GUID كمعرف فريد للجهاز في قاعدة بيانات الخادم
        unique_hw_identifier_for_server_db = f"{device_serial_from_report}_{machine_guid_from_report}"
        
        final_client_id_to_return = None
        generated_license_key = None
        device_already_existed = False

        # ابحث إذا كان هذا الجهاز (بناءً على unique_hw_identifier_for_server_db) مسجلًا بالفعل
        for s_id, dev_info in registered_devices.items():
            if dev_info.get('unique_hw_id') == unique_hw_identifier_for_server_db:
                final_client_id_to_return = s_id # أعد استخدام الـ client_id (الـ UUID) القديم
                generated_license_key = dev_info.get('license_key') # أعد استخدام مفتاح الترخيص القديم
                # يمكنك تحديث بعض المعلومات إذا أردت
                dev_info['last_full_registration_utc'] = current_time_utc.isoformat()
                dev_info['device_name'] = device_name_from_payload
                device_already_existed = True
                message = "Device re-validated and license confirmed."
                print(f"REGISTER_REVALIDATED: Device '{unique_hw_identifier_for_server_db}'. ClientID: {final_client_id_to_return}")
                break
        
        if not device_already_existed:
            final_client_id_to_return = str(uuid.uuid4()) # توليد UUID جديد كـ client_id
            generated_license_key = f"ESK_LIC_{final_client_id_to_return[:8].upper()}_{os.urandom(6).hex().upper()}"
            
            registered_devices[final_client_id_to_return] = {
                'unique_hw_id': unique_hw_identifier_for_server_db,
                'device_name': device_name_from_payload,
                'license_key': generated_license_key,
                'stored_serial_for_ref': device_serial_from_report, # للتأكيد فقط، ليس للاستخدام في الهاش لاحقًا
                'stored_guid_for_ref': machine_guid_from_report,   # للتأكيد فقط
                'registration_utc': current_time_utc.isoformat(),
                'last_full_registration_utc': current_time_utc.isoformat(),
                # يمكنك تخزين ملخص من full_report إذا أردت
                'report_summary': { 
                   "os": full_report.get("OperatingSystem",{}).get("System"),
                   "cpu": full_report.get("Hardware",{}).get("CPU",{}).get("Name")
                }
            }
            message = "Device registered and license generated successfully!"
            print(f"REGISTER_NEW_SUCCESS: Device '{unique_hw_identifier_for_server_db}'. ClientID: {final_client_id_to_return}")
        
        response_payload = {
            "status": "success",
            "message": message,
            "client_id": final_client_id_to_return,
            "license_key": generated_license_key
        }
        print(f"REGISTER_RESPONSE_PAYLOAD: {response_payload}")
        return jsonify(response_payload), 200

    except Exception as e:
        print(f"REGISTER_EXCEPTION (Comprehensive): {e}")
        import traceback
        print(traceback.format_exc()) # مهم جدًا لرؤية الخطأ الكامل في سجلات Render/المحلية
        return jsonify({"error": "Internal server error during comprehensive registration", "details": str(e)}), 500

# ... (بقية نقاط النهاية /heartbeat و / كما هي، مع تحديث استخدام datetime.datetime.now(datetime.timezone.utc))

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