#!/bin/bash
# TeachProxy Admin Panel Startup Script

echo "🎓 Starting TeachProxy Admin Panel..."

# Check if running from correct directory
if [ ! -f "admin/streamlit_app.py" ]; then
    echo "❌ Error: Please run from project root directory"
    echo "Usage: ./scripts/start_admin.sh"
    exit 1
fi

# Load environment variables
if [ -f ".env" ]; then
    echo "📋 Loading environment from .env"
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check if ADMIN_TOKEN is set
if [ -z "$ADMIN_TOKEN" ]; then
    echo "⚠️  Warning: ADMIN_TOKEN not set"
    echo "   Set it in .env file or run: export ADMIN_TOKEN=your_token"
fi

# Check database connectivity
echo "🔌 Checking database connection..."
cd /Users/wangxq/Documents/python
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
try:
    from admin.db_utils_v2 import get_dashboard_stats
    stats = get_dashboard_stats()
    print(f"✅ Database connected: {stats['students']} students found")
except Exception as e:
    print(f"❌ Database error: {e}")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "❌ Database connection failed"
    exit 1
fi

# Start Streamlit
echo "🚀 Starting Streamlit server..."
echo "🌐 Admin panel will be available at: http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop"
echo "=============================================="

streamlit run admin/streamlit_app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
