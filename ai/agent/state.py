from dataclasses import dataclass, field


@dataclass
class EstadoAgente:
    mensagens: list[dict] = field(
        default_factory=list
    )

    def adicionar_mensagem(
        self,
        role: str,
        content: str
    ) -> None:

        self.mensagens.append({
            "role": role,
            "content": content
        })