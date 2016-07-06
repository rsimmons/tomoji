build:
	@docker build -t rsimmons/tomoji .

publish: build
	@docker push rsimmons/tomoji

.PHONY: build publish
