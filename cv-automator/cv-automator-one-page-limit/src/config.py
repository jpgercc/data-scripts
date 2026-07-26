"""
config.py — Configuração centralizada via pydantic-settings.

Carrega variáveis de .env ou do ambiente do sistema.
Nenhuma chave é hardcoded aqui.
"""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Chaves de API ─────────────────────────────────────────
    router_api_key: str = Field(default="", alias="NINE_ROUTER_API_KEY")
    router_base_url: str = Field(
        default="http://127.0.0.1:20128/v1", alias="NINE_ROUTER_BASE_URL"
    )

    # ── Provedor e modelo de IA ───────────────────────────────
    ai_provider: str = Field(default="9router", alias="AI_PROVIDER")
    ai_model: str = Field(default="", alias="AI_MODEL")

    # ── Diretórios ────────────────────────────────────────────
    output_dir: Path = Field(default=Path("output"), alias="OUTPUT_DIR")
    template_dir: Path = Field(default=Path("templates"), alias="TEMPLATE_DIR")
    data_dir: Path = Field(default=Path("data"), alias="DATA_DIR")

    # ── Caminhos derivados (não configuráveis via .env) ───────
    @property
    def template_path(self) -> Path:
        return self.template_dir / "curriculo.typ"

    @property
    def perfil_path(self) -> Path:
        return self.data_dir / "perfil_mestre.json"

    @property
    def effective_model(self) -> str:
        """Retorna o modelo configurado ou o padrão do provedor."""
        if self.ai_model:
            return self.ai_model
        defaults = {
            # Altere para um modelo ou Combo disponível no seu 9Router.
            "9router": "cc/claude-opus-4-7",
        }
        return defaults.get(self.ai_provider, "cc/claude-opus-4-7")

    def validate_provider_key(self) -> None:
        """Levanta ValueError se a chave do provedor ativo estiver ausente."""
        if self.ai_provider.lower() != "9router":
            raise ValueError(
                "AI_PROVIDER inválido. Use '9router'."
            )
        if not self.router_api_key:
            raise ValueError(
                "NINE_ROUTER_API_KEY não configurada. "
                "Defina-a no arquivo .env ou como variável de ambiente."
            )
        if not self.router_base_url:
            raise ValueError(
                "NINE_ROUTER_BASE_URL não configurada. "
                "Defina-a no arquivo .env ou como variável de ambiente."
            )


# Instância única compartilhada por todo o projeto
settings = Settings()
