# Security

Do not include Bark device URLs/keys, SSH credentials, private configuration, or raw conversation payloads in issues or logs. Revoke a leaked Bark key through the receiving app/server.

Report security issues through the repository's private vulnerability reporting feature when available. Otherwise contact the maintainer through GitHub to arrange private disclosure before sharing sensitive details. Avoid posting exploitable details in a public issue.

Pushes use the chosen Bark server and its transport. HTTPS is recommended. The optional SOCKS extension binds only to remote loopback, but any process sharing that network namespace can use it; it does not provide SOCKS authentication.

Diagnostics omit keys and raw responses. Hook trust remains a user decision. No notification queue is persisted; the local history retains only the latest 20 delivery summaries.
