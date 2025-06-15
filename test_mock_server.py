from flask import Flask, request, jsonify
import datetime
import os # لاستخدام متغيرات البيئة للمنفذ

app = Flask(__name__)

# بيانات محاكاة (ستُعاد تهيئتها مع كل إعادة تشغيل للخادم على Render في الطبقة المجانية)
registered_devices = {}
next_client_id_counter = 1001

@app.route('/api/v1/device/register', methods=['POST'])
def register_device():
    global next_client_id_counter
    print("\n--- Received /register request (new fingerprint logic) ---")
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "JSON body expected."}), 400
        print(f"Request JSON: {data}")

        # استخراج البيانات من الكلاينت
        client_sent_serial = data.get('device_serial_number')
        client_sent_guid = data.get('machine_guid')
        client_sent_timestamp_salt = data.get('timestamp_salt')
        client_sent_hash = data.get('fingerprint_hash')
        device_name = data.get('device_name', 'Unknown Device')

        if not all([client_sent_serial, client_sent_guid, client_sent_timestamp_salt, client_sent_hash]):
            return jsonify({"error": "Missing required fields: device_serial_number, machine_guid, timestamp_salt, fingerprint_hash"}), 400

        # (اختياري) التحقق من صحة التوقيت (timestamp_salt) هنا إذا أردت

        # الخادم يعيد حساب الهاش باستخدام البيانات المستلمة (لأن هذه هي بيانات "الهوية" الآن)
        # والملح (التوقيت) المستلم.
        hash_calculated_by_server = calculate_server_hash( # استخدم دالة حساب الهاش على الخادم
            client_sent_serial,
            client_sent_timestamp_salt,
            client_sent_guid
        )

        if hash_calculated_by_server is None:
            return jsonify({"error": "Server error during hash calculation."}), 500

        print(f"Server calculated hash: {hash_calculated_by_server}")
        print(f"Client provided hash:   {client_sent_hash}")

        if hashlib.compare_digest(hash_calculated_by_server, client_sent_hash):
            # الهاش متطابق! هذا يعني أن الكلاينت أرسل بصمة صحيحة
            # بناءً على السيريال والـ GUID والتوقيت الذي أرسلهم.

            # الآن منطق التسجيل/التحديث:
            # ابحث عن جهاز بناءً على مزيج فريد (مثلاً، client_sent_serial + client_sent_guid)
            # هذا يعتمد على كيف تريد تعريف "الجهاز الفريد"
            unique_device_identifier_on_server = f"{client_sent_serial}_{client_sent_guid}" # مثال

            server_client_id_to_return = None
            found_device = False
            for s_id, dev_info in registered_devices.items():
                if dev_info.get('unique_hw_id') == unique_device_identifier_on_server:
                    server_client_id_to_return = s_id
                    dev_info['last_verified_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    dev_info['device_name'] = device_name # تحديث الاسم
                    found_device = True
                    message = "Device re-authenticated successfully."
                    print(f"Device '{unique_device_identifier_on_server}' re-authenticated. Server ClientID: {s_id}")
                    break
            
            if not found_device:
                server_client_id_to_return = f"RNDR_AUTH_CLNT_{next_client_id_counter}"
                next_client_id_counter += 1
                registered_devices[server_client_id_to_return] = {
                    'unique_hw_id': unique_device_identifier_on_server,
                    'device_name': device_name,
                    'device_serial_stored': client_sent_serial, # حفظ المعلومات للتحققات المستقبلية
                    'machine_guid_stored': client_sent_guid,   # إذا لم تكن هي نفسها unique_hw_id
                    'first_registered_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'last_verified_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()
                }
                message = "Device authenticated and registered successfully!"
                print(f"New device '{unique_device_identifier_on_server}' authenticated. Assigned Server ClientID: {server_client_id_to_return}")

            response_data = {
                "message": message,
                "client_id": server_client_id_to_return,
                "status": "success"
            }
            return jsonify(response_data), 200
        else:
            print("Error: Fingerprint hash mismatch between client and server calculation.")
            return jsonify({"error": "Fingerprint verification failed. Hash mismatch.", "status": "unauthorized"}), 401

    except Exception as e:
        print(f"Error processing /register request: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "An internal server error occurred", "details": str(e)}), 500


@app.route('/api/v1/device/heartbeat', methods=['POST'])
def heartbeat():
    print("\n--- Received /heartbeat request ---")
    try:
        client_id_from_header = request.headers.get('X-Device-ID')
        print(f"X-Device-ID Header: {client_id_from_header}")

        # جسم الطلب (payload) من الكلاينت يفترض أن يكون JSON فارغ {} أو بيانات أخرى
        # request_payload = request.get_json() # إذا كنت تتوقع جسمًا
        # print(f"Request JSON Payload: {request_payload}")

        if not client_id_from_header:
            print("Error: 'X-Device-ID' header is missing.")
            return jsonify({"error": "X-Device-ID header is required"}), 400

        if client_id_from_header in registered_devices:
            registered_devices[client_id_from_header]['last_seen'] = datetime.datetime.utcnow().isoformat() + "Z"
            message = "Heartbeat acknowledged by Render mock server."
            print(f"Heartbeat received for ClientID: {client_id_from_header}")
            response_data = {
                "message": message,
                "status": "success",
                "data": {"timestamp": datetime.datetime.utcnow().isoformat() + "Z"} # مثال على بيانات إضافية
            }
            return jsonify(response_data), 200
        else:
            message = "Device not recognized by Render mock server."
            print(f"Heartbeat rejected for unknown ClientID: {client_id_from_header}")
            return jsonify({"error": message, "status": "unauthorized"}), 401

    except Exception as e:
        print(f"Error processing /heartbeat request: {e}")
        return jsonify({"error": "An internal server error occurred", "details": str(e)}), 500

# نقطة نهاية بسيطة للتحقق من أن الخادم يعمل
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "Render Mock Server is UP!", "time": datetime.datetime.utcnow().isoformat() + "Z"}), 200

if __name__ == '__main__':
    # Render ستقوم بتعيين متغير البيئة PORT
    # محليًا، إذا لم يتم تعيينه، سيستخدم 5500
    port = int(os.environ.get('PORT', 5500))
    # مهم: يجب أن يستمع على 0.0.0.0 ليقبل الاتصالات الخارجية على Render
    app.run(host='0.0.0.0', port=port, debug=False) # debug=False للإنتاج على Render