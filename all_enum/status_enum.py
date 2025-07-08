
from enum import Enum


class CategoriaProduto(str, Enum):
    VESTUARIO = "Vestuário"
    DECORACAO = "Decoração"
    ELETRONICOS = "Eletrônicos"
    BRINQUEDOS = "Brinquedos"

class FormaPagamento(str, Enum):
    CARTAO_CREDITO = "Cartão de Crédito"
    CARTAO_DEBITO = "Cartão de Débito"
    PIX = "Pix"
    BOLETO = "Boleto"
    TRANSFERENCIA = "Transferência"
    
class StatusPedido(str, Enum):
    PENDENTE = "Pendente"
    PROCESSANDO = "Processando"
    ENVIADO = "Enviado"
    ENTREGUE = "Entregue"
    CANCELADO = "Cancelado"
 
class TipoDesconto(str, Enum):
    PORCENTAGEM = "porcentagem"
    VALOR_FIXO = "valor_fixo"