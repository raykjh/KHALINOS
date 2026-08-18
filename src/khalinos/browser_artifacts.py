"""Text-only structured output for Gemini browser makers.

Binary assets are deliberately absent. Only the trusted host may promote this output into
an ArtifactBundle and attach a validated asset sidecar.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

from khalinos.models import ArtifactBundle, ArtifactFile


EXTERNAL_CSS_IMPORT = re.compile(r"(?im)^\s*@import\s+[^;\r\n]*https?://[^;\r\n]*;\s*")


class BrowserArtifactFile(ArtifactFile):
    path: str = Field(pattern=r"^(index\.html|styles\.css|app\.js|journey\.json|README\.md)$")
    content: str = Field(min_length=1, max_length=50_000)


class BrowserArtifactBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_summary: str = Field(min_length=10, max_length=500)
    files: list[BrowserArtifactFile] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def complete_browser_surface(self) -> "BrowserArtifactBundle":
        expected = {"index.html", "styles.css", "app.js", "journey.json", "README.md"}
        if {item.path for item in self.files} != expected:
            raise ValueError("browser artifact must contain the complete five-file surface")
        return self

    def to_artifact_bundle(self) -> ArtifactBundle:
        normalized: list[ArtifactFile] = []
        removed_external_import = False
        for item in self.files:
            content = item.content
            if item.path == "styles.css":
                content, removed = EXTERNAL_CSS_IMPORT.subn("", content)
                removed_external_import = removed > 0
            normalized.append(ArtifactFile(path=item.path, content=content))
        summary = self.revision_summary
        if removed_external_import:
            summary = f"{summary} Trusted host removed prohibited external CSS imports."
        return ArtifactBundle(revision_summary=summary[:2000], files=normalized)
