# TO DO LIST

1.
inves de recriar o modelo base como por EXEMPLO em:
``` txt
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
```

Essas informações deveriam ser puxadas direto de perfil_mestre.json, assim caso o usuario adicione ou remova alguma linha, o código continua funcionando normalmente

2. 
Main deveria ter apenas referencia propria, sem orquestrar nada, o orquestramento pode ser feito em um novo arquivo como um run.py

3.
config.py deveria ser realmente util, deveria conter:
- ai configs (noise removal, prompts and every AI configure variable)
- .pdf config (so user can select if he want to limit .pdf pages or use smaller fonts to fit, etc.)
