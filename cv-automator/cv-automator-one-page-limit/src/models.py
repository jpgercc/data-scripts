"""
models.py — Schemas Pydantic para validação da resposta da IA.

Toda resposta da IA passa por estes modelos antes de ser usada.
Respostas inválidas são rejeitadas, nunca silenciadas.
"""

from typing import Any
from pydantic import BaseModel, Field, model_validator


class Experience(BaseModel):
    empresa: str = Field(..., min_length=1)
    cargo: str = Field(..., min_length=1)
    periodo: str = Field(..., min_length=1)
    responsabilidades: list[str] = Field(..., min_length=1)

    @model_validator(mode="after")
    def responsabilidades_nao_vazias(self) -> "Experience":
        if any(r.strip() == "" for r in self.responsabilidades):
            raise ValueError("Nenhuma responsabilidade pode ser uma string vazia.")
        return self


class Education(BaseModel):
    instituicao: str = Field(..., min_length=1)
    curso: str = Field(..., min_length=1)
    periodo: str = Field(..., min_length=1)


class Language(BaseModel):
    idioma: str = Field(..., min_length=1)
    nivel: str = Field(..., min_length=1)


class Curriculum(BaseModel):
    nome: str = Field(..., min_length=1)
    titulo: str = Field(..., min_length=1)
    email: str = Field(..., min_length=1)
    telefone: str = Field(..., min_length=1)
    linkedin: str = Field(default="")
    github: str = Field(default="")
    localizacao: str = Field(default="")
    resumo: str = Field(..., min_length=20)
    experiencias: list[Experience] = Field(..., min_length=1)
    habilidades: dict[str, Any] = Field(..., min_length=1)
    formacao: list[Education] = Field(..., min_length=1)
    certificacoes: list[str] = Field(default_factory=list)
    idiomas: list[Language] = Field(default_factory=list)
