DROPLET := root@159.65.241.127
REMOTE_PATH := /root/platform-infra

.PHONY: diff sync deploy

# Show diff between local and server configs
diff:
	@echo "=== Caddyfile ==="
	@ssh $(DROPLET) "cat $(REMOTE_PATH)/Caddyfile" | diff - Caddyfile || true
	@echo ""
	@echo "=== docker-compose.yml ==="
	@ssh $(DROPLET) "cat $(REMOTE_PATH)/docker-compose.yml" | diff - docker-compose.yml || true

# Sync with confirmation if there are server-only changes
sync:
	@echo "Checking for server-only changes..."
	@if ssh $(DROPLET) "cat $(REMOTE_PATH)/Caddyfile" | diff -q - Caddyfile >/dev/null 2>&1 && \
	    ssh $(DROPLET) "cat $(REMOTE_PATH)/docker-compose.yml" | diff -q - docker-compose.yml >/dev/null 2>&1; then \
		echo "No conflicts. Syncing..."; \
		rsync -avz --exclude='.git' --exclude='.env' ./ $(DROPLET):$(REMOTE_PATH)/; \
	else \
		echo "WARNING: Server has changes not in local repo. Run 'make diff' to see them."; \
		read -p "Sync anyway? [y/N] " confirm && [ "$$confirm" = "y" ] && \
		rsync -avz --exclude='.git' --exclude='.env' ./ $(DROPLET):$(REMOTE_PATH)/; \
	fi

# Deploy a specific service (usage: make deploy SERVICE=noodle)
deploy:
	@if [ -z "$(SERVICE)" ]; then echo "Usage: make deploy SERVICE=<name>"; exit 1; fi
	ssh $(DROPLET) "cd $(REMOTE_PATH) && docker compose pull $(SERVICE) && docker compose up -d $(SERVICE)"
