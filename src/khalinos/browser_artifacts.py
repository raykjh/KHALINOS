"""Browser ToolPack-specific structured-output schema for Gemini makers."""

from __future__ import annotations

from pydantic import Field, model_validator

from khalinos.models import ArtifactBundle, ArtifactFile


class BrowserArtifactFile(ArtifactFile):
    path: str = Field(pattern=r"^(index\.html|styles\.css|app\.js|journey\.json|README\.md)$")
    content: str = Field(min_length=1, max_length=50_000)


class BrowserArtifactBundle(ArtifactBundle):
    files: list[BrowserArtifactFile] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def complete_browser_surface(self) -> "BrowserArtifactBundle":
        expected = {"index.html", "styles.css", "app.js", "journey.json", "README.md"}
        if {item.path for item in self.files} != expected:
            raise ValueError("browser artifact must contain the complete five-file surface")
        return self
