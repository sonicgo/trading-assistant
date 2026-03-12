# Trading Assistant Operations Runbook

## Table of Contents

1. [Starting and Stopping the Application](#starting-and-stopping-the-application)
2. [Database Backup and Restore](#database-backup-and-restore)
3. [Monitoring and Logs](#monitoring-and-logs)
4. [Troubleshooting](#troubleshooting)
5. [Health Checks](#health-checks)

---

## Starting and Stopping the Application

### Start the Full Stack

```bash
# Start all services (API, Worker, Database, Redis)
docker compose up -d

# Verify all services are running
docker compose ps
```

### Stop the Application

```bash
# Stop all services gracefully
docker compose down

# Stop and remove volumes (WARNING: deletes database data)
docker compose down -v
```

### Restart Individual Services

```bash
# Restart the API service
docker compose restart api

# Restart the worker service
docker compose restart worker

# Restart the database
docker compose restart db
```

### View Service Status

```bash
# Check running containers
docker compose ps

# Check resource usage
docker stats
```

---

## Database Backup and Restore

### Creating a Backup

The backup script creates a timestamped PostgreSQL dump in the `backups/` directory.

```bash
# Create a standard backup
./scripts/backup_db.sh

# Create a compressed backup (recommended for large databases)
./scripts/backup_db.sh --compress

# Show help
./scripts/backup_db.sh --help
```

**Output:**
- Backups are stored in: `backups/trading_assistant_YYYYMMDD_HHMMSS.sql`
- Compressed backups: `backups/trading_assistant_YYYYMMDD_HHMMSS.sql.gz`
- The script automatically keeps only the last 10 backups

### Restoring from Backup

**WARNING:** Restoring will DROP the current database and replace it with the backup. All current data will be lost.

```bash
# List available backups
ls -la backups/

# Restore from a backup (interactive confirmation)
./scripts/restore_db.sh trading_assistant_20240311_120000.sql

# Restore with force flag (no confirmation)
./scripts/restore_db.sh --force trading_assistant_20240311_120000.sql.gz

# Show help
./scripts/restore_db.sh --help
```

**Post-Restore Verification:**

After restore, the script automatically:
1. Verifies tables exist in the database
2. Restarts the API and worker services
3. Reports service startup status

Wait 10-15 seconds after restore before accessing the application.

### Manual Database Operations

```bash
# Connect to database shell
docker compose exec db psql -U ta_app -d trading_assistant

# Execute a SQL query
docker compose exec db psql -U ta_app -d trading_assistant -c "SELECT COUNT(*) FROM portfolio;"

# Export specific table
docker compose exec db pg_dump -U ta_app -d trading_assistant --table=portfolio > portfolio_backup.sql
```

---

## Monitoring and Logs

### Viewing Service Logs

```bash
# View all service logs
docker compose logs

# View logs for specific service
docker compose logs api
docker compose logs worker
docker compose logs db

# Follow logs in real-time
docker compose logs -f

# View last 100 lines
docker compose logs --tail 100 api
```

### Checking Background Scheduler Logs

The APScheduler runs inside the API container and logs to stdout:

```bash
# View scheduler logs (part of API logs)
docker compose logs api | grep -i scheduler

# View retention job logs
docker compose logs api | grep -i retention

# View all job execution logs
docker compose logs api | grep -E "(scheduler|job|executed|failed)"
```

### Monitoring Scheduled Jobs

The scheduler runs the following jobs:
- **Weekly Retention Cleanup**: Sundays at 02:00 London time
  - Cleans up execution logs older than 30 days
  - Logs show: "Scheduled retention job 'weekly_retention_cleanup'"

To verify scheduler is running:
```bash
docker compose logs api | grep "Scheduler initialized"
```

### Log Rotation

Logs are managed by Docker's logging driver. To clear logs:

```bash
# Clear logs for a specific container
docker compose logs api > /dev/null

# Or truncate log files directly
docker compose exec api sh -c "truncate -s 0 /proc/1/fd/1"
```

---

## Troubleshooting

### Application Won't Start

```bash
# Check container status
docker compose ps

# Check for port conflicts
docker compose logs api | grep -i "address already in use"

# Verify environment variables
docker compose config

# Check database connection
docker compose exec api python -c "from app.db.session import engine; print('DB connection OK')"
```

### Database Connection Issues

```bash
# Check if database is running
docker compose ps db

# Check database logs
docker compose logs db

# Test database connectivity
docker compose exec db pg_isready -U ta_app

# Restart database
docker compose restart db
```

### Worker Not Processing Jobs

```bash
# Check worker logs
docker compose logs worker

# Restart worker
docker compose restart worker

# Check Redis connection
docker compose exec worker python -c "import redis; r = redis.Redis(host='redis'); print(r.ping())"
```

### Scheduler Not Running

```bash
# Check API logs for scheduler initialization
docker compose logs api | grep -i scheduler

# Should see: "Scheduler initialized (single-worker mode)"

# Restart API to reinitialize scheduler
docker compose restart api
```

### Restore Failures

```bash
# Check if backup file is valid
docker compose exec db pg_restore --list < backup_file.sql 2>&1 | head -20

# Check available disk space
docker system df

# Verify database container is healthy
docker compose ps db
```

---

## Health Checks

### Application Health Endpoint

```bash
# Check application health
curl http://localhost:8000/health

# Expected response: {"status": "ok"}

# Check readiness
curl http://localhost:8000/ready

# Expected response: {"status": "ready"}
```

### Database Health

```bash
# Check database connectivity
docker compose exec db psql -U ta_app -d trading_assistant -c "SELECT version();"

# Check table counts
docker compose exec db psql -U ta_app -d trading_assistant -c "
SELECT schemaname, tablename, n_tup_ins - n_tup_del as row_count
FROM pg_stat_user_tables
ORDER BY n_tup_ins - n_tup_del DESC
LIMIT 10;
"
```

### Service Status Summary

```bash
# Quick health check script
echo "=== Trading Assistant Health Check ==="
echo ""
echo "Container Status:"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}"
echo ""
echo "API Health:"
curl -s http://localhost:8000/health | jq .
echo ""
echo "Database Connection:"
docker compose exec -T db pg_isready -U ta_app -d trading_assistant
echo ""
echo "Recent API Logs:"
docker compose logs --tail 5 api
```

---

## Quick Reference

### Common Commands

| Task | Command |
|------|---------|
| Start services | `docker compose up -d` |
| Stop services | `docker compose down` |
| View logs | `docker compose logs -f` |
| Backup database | `./scripts/backup_db.sh --compress` |
| Restore database | `./scripts/restore_db.sh backup_file.sql` |
| Restart API | `docker compose restart api` |
| Check health | `curl http://localhost:8000/health` |
| DB shell | `docker compose exec db psql -U ta_app -d trading_assistant` |

### File Locations

| File/Directory | Path |
|----------------|------|
| Backups | `./backups/` |
| Backup script | `./scripts/backup_db.sh` |
| Restore script | `./scripts/restore_db.sh` |
| Environment config | `./.env` |
| Docker Compose | `./docker-compose.yml` |
| API logs | `docker compose logs api` |
| Worker logs | `docker compose logs worker` |

---

## Support

For issues not covered in this runbook:

1. Check the [Phase 5/6 Build Playbook](../implementation/Phase5_phase6_build_playbook.md)
2. Review application logs: `docker compose logs`
3. Verify system requirements in README.md
