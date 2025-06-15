from flask import Flask, request, jsonify
import datetime
import os # لاستخدام متغيرات البيئة للمنفذ

app = Flask(__name__)

# بيانات محاكاة (ستُعاد تهيئتها مع كل إعادة تشغيل للخادم على Render في الطبقة المجانية)
registered_devices = {}
next_client_id_counter = 1001

@app.route('/api/v1/device/register', methods=['POST'])
def register_device():
    global next_client_id_counter # ضروري لتعديل المتغير العام
    print("\n--- Received /register request ---") # للـ logging على Render
    try:
        data = request.get_json()
        if not data: # إذا لم يتم إرسال JSON
            print("Error: Request body is not JSON or is empty.")
            return jsonify({"error": "Invalid request. JSON body expected."}), 400
        print(f"Request JSON: {data}")


        device_id_from_client = data.get('device_id')
        device_name = data.get('device_name', 'Unknown Device')

        if not device_id_from_client:
            print("Error: 'device_id' is missing in request.")
            return jsonify({"error": "Device ID is required"}), 400

        existing_client_id = None
        for client_id, dev_info in registered_devices.items():
            if dev_info['original_device_id'] == device_id_from_client:
                existing_client_id = client_id
                break

        if existing_client_id:
            registered_devices[existing_client_id]['last_seen'] = datetime.datetime.utcnow().isoformat() + "Z"
            registered_devices[existing_client_id]['device_name'] = device_name
            client_id_to_return = existing_client_id
            message = "Device already known. Information possibly updated."
            print(f"Device '{device_id_from_client}' already known with ClientID: {client_id_to_return}.")
        else:
            client_id_to_return = f"RNDR_CLNT_{next_client_id_counter}" # RNDR لـ Render
            next_client_id_counter += 1
            registered_devices[client_id_to_return] = {
                'original_device_id': device_id_from_client,
                'device_name': device_name,
                'registered_at': datetime.datetime.utcnow().isoformat() + "Z",
                'last_seen': datetime.datetime.utcnow().isoformat() + "Z"
            }
            message = "Device registered successfully on Render!"
            print(f"New device '{device_id_from_client}' registered. Assigned ClientID: {client_id_to_return}")

        response_data = {
            "message": message,
            "client_id": client_id_to_return,
            "status": "success",
            "server_type": "Render Mock"
        }
        print(f"Sending response: {response_data}")
        return jsonify(response_data), 200

    except Exception as e:
        print(f"Error processing /register request: {e}")
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