"""Validated inputs for live publisher identity collection."""

from pydantic import BaseModel, Field, model_validator

from services.publisher_lookup_service import normalize_domain


class PublisherLookupRequest(BaseModel):
    buyer_id: str = Field(min_length=1, max_length=40, pattern=r"^[0-9]+$")
    app_id: str | None = Field(
        default=None,
        max_length=255,
        pattern=r"^(?:[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+|[0-9]+)$",
    )
    domain: str | None = Field(default=None, max_length=500)
    publisher_name: str | None = Field(default=None, min_length=2, max_length=200)
    include_google: bool = True

    @model_validator(mode="after")
    def validate_identity(self):
        if self.publisher_name:
            self.publisher_name = self.publisher_name.strip()
            if len(self.publisher_name) < 2:
                raise ValueError("publisher_name must contain at least two characters")
        if not self.app_id and not self.domain and not self.publisher_name:
            raise ValueError("app_id, domain or publisher_name is required")
        if not self.app_id and not self.domain and not self.include_google:
            raise ValueError("A publisher_name-only search requires include_google")
        if self.domain:
            self.domain = normalize_domain(self.domain)
        return self
