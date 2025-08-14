#!/bin/bash

SCRIPT_DIR="/home/ubuntu/upak-bot"
SERVICE_NAME="upak-bot"

case "$1" in
    start)
        echo "🚀 Starting UPAK Bot..."
        sudo systemctl start $SERVICE_NAME
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    stop)
        echo "🛑 Stopping UPAK Bot..."
        sudo systemctl stop $SERVICE_NAME
        ;;
    restart)
        echo "🔄 Restarting UPAK Bot..."
        sudo systemctl restart $SERVICE_NAME
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    status)
        echo "📊 UPAK Bot Status:"
        sudo systemctl status $SERVICE_NAME --no-pager
        echo ""
        echo "📊 Recent logs:"
        sudo journalctl -u $SERVICE_NAME --no-pager -n 10
        ;;
    logs)
        echo "📄 UPAK Bot Logs:"
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    test)
        echo "🧪 Testing bot functionality..."
        cd $SCRIPT_DIR
        export $(grep -v '^#' .env | xargs)
        curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN/getMe" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('ok'):
    bot = data['result'] 
    print(f'✅ Bot: {bot[\"first_name\"]} (@{bot.get(\"username\", \"N/A\")})')
    print(f'✅ ID: {bot[\"id\"]}')
    print('✅ Bot is accessible via Telegram API')
else:
    print('❌ Bot API test failed')
"
        ;;
    *)
        echo "UPAK Bot Manager"
        echo "Usage: $0 {start|stop|restart|status|logs|test}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the bot service"
        echo "  stop    - Stop the bot service" 
        echo "  restart - Restart the bot service"
        echo "  status  - Show bot status and recent logs"
        echo "  logs    - Follow bot logs in real-time"
        echo "  test    - Test bot API connectivity"
        ;;
esac