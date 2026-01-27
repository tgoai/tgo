-- Seed a sample email platform for testing
-- This creates an email platform with IMAP configuration for inbound email fetching
-- Note: Outbound SMTP is now configured globally via SMTP_* environment variables

INSERT INTO pt_platforms (id, project_id, name, type, config, is_active)
VALUES (
  gen_random_uuid(),
  gen_random_uuid(),
  'Support Email',
  'email',
  '{
     "imap_host": "imap.gmail.com",
     "imap_port": 993,
     "imap_username": "support@example.com",
     "imap_password": "your-app-password-here",
     "imap_use_ssl": true,
     "mailbox": "INBOX",
     "poll_interval_seconds": 60
   }'::jsonb,
  true
)
ON CONFLICT DO NOTHING;

-- Verify the insert
SELECT id, project_id, name, type, is_active, created_at 
FROM pt_platforms 
WHERE type = 'email'
ORDER BY created_at DESC
LIMIT 5;

