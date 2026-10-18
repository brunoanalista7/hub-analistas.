# Segurança e dados

## Quem vê o quê

| O quê | TV da sala | App (analistas) |
|---|---|---|
| Presença e "desde quando" | Sim | Sim |
| Demandas normais (título, pasta, quem pediu, prazo) | Sim | Sim |
| Demanda **reservada** | Só "Demanda reservada", a cor e as iniciais do dono e o prazo | Tudo |
| Histórico | Não | Sim |

A demanda reservada é mascarada **no servidor**: a página da TV nunca recebe o título, então nem quem inspecionar a página consegue ver.

## Presença

Marcada **sempre pela própria pessoa**. O Hub não detecta nada sozinho: não olha login, câmera, Wi-Fi nem atividade do computador. À meia-noite todos voltam para "Fora da empresa", para ninguém aparecer na sala sem estar.

## Onde ficam os dados

| O quê | Onde | Vai para o GitHub? |
|---|---|---|
| Código, documentação, testes | pasta do projeto | Sim |
| Equipe, demandas, presença, histórico | `%LOCALAPPDATA%\Hub\hub.db` no PC reserva | **Não** |
| Cópias diárias (14 dias) | `%LOCALAPPDATA%\Hub\copias` | **Não** |
| Dados de demonstração | criados na hora por `tools/seed_demo.py`, com nomes **fictícios** | O script sim; os dados não |

Nada sai da rede da empresa: sem nuvem, sem telemetria, sem terceiros.

## Acesso

- **Sem senha na versão 1.** Cada pessoa escolhe o próprio nome uma vez, e o navegador lembra. Faz sentido para uma equipe pequena numa rede interna. O histórico registra quem fez cada mudança.
- Formulários enviados a partir de **outro site** são recusados (verificação de mesma origem).
- O Hub fica acessível a quem estiver na rede da empresa e souber o endereço. Se isso não for aceitável, o próximo passo é um PIN por pessoa (roadmap).
