# Athena Audit Queries (Examples)

## Sends by buyer per day
```sql
SELECT date, buyer, status, count(*) AS n
FROM send_events
WHERE date BETWEEN '2026-02-01' AND '2026-02-26'
GROUP BY date, buyer, status
ORDER BY date DESC, n DESC;
```

## Top blocked reasons
```sql
SELECT date, reason, count(*) AS n
FROM send_events
WHERE status = 'blocked'
GROUP BY date, reason
ORDER BY n DESC;
```
