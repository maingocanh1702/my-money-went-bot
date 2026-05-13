.PHONY: install-hooks
install-hooks:
	ln -sf ../../scripts/git-hooks/pre-push.sh .git/hooks/pre-push
	@echo "✓ Pre-push hook installed"
