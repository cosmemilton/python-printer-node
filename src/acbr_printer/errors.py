"""Erros estruturados, sem payload fiscal ou diagnóstico bruto do filho."""


class ErroAcbrImpressora(Exception):
    def __init__(self, codigo: str, mensagem: str, resultado_incerto: bool = False,
                 falha_limpeza: bool = False) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.resultado_incerto = resultado_incerto
        self.falha_limpeza = falha_limpeza

    @property
    def resultadoIncerto(self) -> bool:
        return self.resultado_incerto

    @property
    def falhaLimpeza(self) -> bool:
        return self.falha_limpeza

    def to_dict(self) -> dict:
        result = {"codigo": self.codigo, "mensagem": str(self),
                  "resultadoIncerto": self.resultado_incerto}
        if self.falha_limpeza:
            result["falhaLimpeza"] = True
        return result

    toJSON = to_dict
