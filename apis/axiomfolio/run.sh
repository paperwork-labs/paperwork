#!/bin/bash

# AxiomFolio Startup Script
echo "🚀 Starting AxiomFolio Trading Platform..."

# This script is a thin wrapper around the canonical Makefile entrypoint.
# We keep it for convenience/backwards compatibility.

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo "❌ Docker is not running. Please start Docker Desktop and try again."
        exit 1
    fi
    echo "✅ Docker is running"
}

# Function to check if make is available
check_make() {
    if ! command -v make > /dev/null 2>&1; then
        echo "❌ make not found. Please install Xcode Command Line Tools (macOS) and try again."
        exit 1
    fi
    echo "✅ make found"
}

# Ensure infra env files exist (real values are gitignored)
setup_infra_env() {
    mkdir -p infra
    if [ ! -f infra/env.dev ]; then
        echo "📝 Creating infra/env.dev from infra/env.dev.example..."
        cp infra/env.dev.example infra/env.dev
        echo "⚠️  Please edit infra/env.dev with your local configuration (secrets/ports)."
    else
        echo "✅ infra/env.dev exists"
    fi
    if [ ! -f infra/env.test ]; then
        echo "📝 Creating infra/env.test from infra/env.test.example..."
        cp infra/env.test.example infra/env.test
        echo "⚠️  Please edit infra/env.test with your test configuration (safe defaults are fine)."
    else
        echo "✅ infra/env.test exists"
    fi
}

print_urls() {
    # shellcheck disable=SC1091
    source infra/env.dev
    LADLE_HOST_PORT="${LADLE_HOST_PORT:-61000}"
    echo ""
    echo "🌐 Access URLs:"
    echo "   • API Documentation: http://localhost:${BACKEND_HOST_PORT}/docs"
    echo "   • API Health Check: http://localhost:${BACKEND_HOST_PORT}/health"
    echo "   • Frontend: http://localhost:${WEB_HOST_PORT}"
    echo "   • Ladle: http://localhost:${LADLE_HOST_PORT}"
    echo "   • Celery Monitor (Flower): http://localhost:${FLOWER_HOST_PORT}"
    echo "   • PostgreSQL (dev): localhost:${DB_HOST_PORT}"
    echo "   • Redis (dev): localhost:${REDIS_HOST_PORT}"
}

makemigration() {
    MSG="$1"
    if [ -z "$MSG" ]; then
        echo "Usage: $0 makemigration \"message\""
        exit 1
    fi
    echo "🧱 Creating Alembic revision: $MSG"
    make migrate-create MSG="$MSG"
}

downgrade() {
    REV="$1"
    if [ -z "$REV" ]; then
        echo "Usage: $0 downgrade <revision>"
        exit 1
    fi
    echo "↩️  Downgrading to $REV"
    make migrate-down REV="$REV"
}

stamp_head() {
    echo "🏷️  Stamping head"
    make migrate-stamp-head
}

# Main menu
case "$1" in
    start)
        check_docker
        check_make
        setup_infra_env
        echo "🐳 Starting Docker containers (make up)..."
        make up
        make ps
        print_urls
        ;;
    stop)
        check_make
        setup_infra_env
        echo "🛑 Stopping dev stack (make down)..."
        make down
        ;;
    restart)
        check_make
        setup_infra_env
        echo "🔁 Restarting dev stack..."
        make down
        sleep 2
        make up
        make ps
        print_urls
        ;;
    status)
        check_make
        setup_infra_env
        make ps
        print_urls
        ;;
    logs)
        check_make
        setup_infra_env
        make logs
        ;;
    test)
        check_make
        setup_infra_env
        echo "🧪 Running tests in isolated test DB (make test)..."
        make test-up
        make test
        ;;
    makemigration)
        check_make
        setup_infra_env
        makemigration "$2"
        ;;
    migrate)
        check_make
        setup_infra_env
        echo "⬆️  Applying Alembic migrations (dev DB)..."
        make migrate-up
        ;;
    downgrade)
        check_make
        setup_infra_env
        downgrade "$2"
        ;;
    stamp)
        check_make
        setup_infra_env
        stamp_head
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|test|migrate|makemigration|downgrade|stamp}"
        echo ""
        echo "Commands:"
        echo "  start   - Start dev stack (via Makefile)"
        echo "  stop    - Stop dev stack (via Makefile)"
        echo "  restart - Restart dev stack (via Makefile)"
        echo "  status  - Show service status and URLs"
        echo "  logs    - Tail logs (backend/worker/beat/frontend)"
        echo "  test    - Run tests in isolated test DB (postgres_test)"
        echo "  migrate - Apply Alembic migrations to dev DB (upgrade head)"
        echo "  makemigration - Create an autogenerate Alembic revision (dev DB)"
        echo "  downgrade - Alembic downgrade (dev DB)"
        echo "  stamp   - Alembic stamp head (dev DB)"
        exit 1
        ;;
esac