import requests

def send_telegram_alert(message):
    TOKEN = '7933290460:AAEi5wSTxvkx4FAfxaYtgsp8z40PikygWkA'
    CHAT_ID = '6302368759'
    url = f'https://api.telegram.org/bot7933290460:AAEi5wSTxvkx4FAfxaYtgsp8z40PikygWkA/sendMessage'
    payload = {
        'chat_id': CHAT_ID,
        'text': message
    }
    try:
        response = requests.post(url, data=payload)
        print('✅ Telegram alert sent:', response.status_code)
    except Exception as e:
        print('❌ Failed to send Telegram alert:', e)

send_telegram_alert("🚨 Test Alert: SafeDetect is now live!")