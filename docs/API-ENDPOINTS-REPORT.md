# OrchAI — Relatório de Status dos Endpoints da API (v0.1.11)

## Como ler este relatório

Este documento é um raio-x objetivo do que a API HTTP (`src/orchai/interfaces/api/main.py`) realmente faz hoje, verificado por leitura direta do código, pela suíte de testes (124 testes, unitários e de integração) e por chamadas reais rodadas agora contra a API para confirmar os pontos mais sutis. Não é um documento arquitetural (isso já existe em `docs/architecture/API-UI-BOUNDARY.md`) — é um checkpoint de "o que está implementado e funciona" antes de avançarmos para os adapters de IA reais.

> **Atualização v0.1.5:** a seção 9 descrevia uma "surpresa" em `POST /requests` — o estágio PLAN acontecia de forma síncrona e sem gate de política, então a primeira sugestão que o cliente via já era `IMPLEMENT`. Isso não era uma nuance de implementação: contrariava o que `docs/architecture/CHAT-FIRST-REQUEST-MODEL.md` (seção 3) e o invariante nº2 da ADR-011 já especificavam. Foi corrigido nessa sessão.

> **Atualização v0.1.6:** `POST /requests/{id}/approve` passou a resolver o caso comum de `PENDING_SUGGESTION` — quando não existe nenhuma autorização pendente (o caso normal em modo `SUGGESTED` após o gate do PLAN), o endpoint delega internamente para o mesmo mecanismo gated usado por `/advance` (`approve_stage: true`), em vez de sempre responder `no_pending_authorization`. Isso não é um bypass: a chamada delegada ainda passa pela mesma avaliação de política. Ver seção 9.

> **Atualização v0.1.7:** `POST /admin/db/create` e `POST /admin/db/migrate` (e os comandos CLI equivalentes `orchai db create`/`orchai db migrate`) foram **removidos** — `db sync` (`POST /admin/db/sync`, `orchai db sync`) é agora a única operação padrão de administração de banco, cobrindo os dois casos num só passo (cria o banco se necessário — só PostgreSQL, pulado sem erro em SQLite/local-flow — e em seguida aplica as migrações incondicionalmente). Ver seção 2. Esta sessão também sincronizou este relatório e o restante da documentação com o estado real e completo do repositório (a sessão anterior operava sobre uma cópia parcial do projeto, faltando dezenas de documentos e 18 arquivos de teste unitário) — ver `docs/STATUS.md` para o relato completo, incluindo 8 testes unitários pré-existentes que só vieram à tona nesta sincronização e foram corrigidos para refletir o gate do PLAN da v0.1.5.

> **Atualização v0.1.8:** `infrastructure/persistence/sqlite/` e `infrastructure/persistence/postgresql/` foram unificadas em `infrastructure/persistence/db/` (migrações agora em `infrastructure/persistence/db/migrations/*.sql`, aplicadas do mesmo jeito idempotente descrito na seção 2). Nenhum comportamento de endpoint mudou. Ver `docs/STATUS.md` para o relato completo, incluindo a implementação isolada da Fase 1 de Identidade e Controle de Acesso (`docs/TO-DO.md` Prioridade 1) — ainda sem nenhuma rota ou comando exposto.

> **Atualização v0.1.9:** Fase 2 de Identidade e Controle de Acesso implementada (`docs/TO-DO.md` Prioridade 1): emissão/validação de access tokens JWT (`JWTAccessTokenIssuer`) e hashing de refresh tokens via SHA-256 (`Sha256RefreshTokenHasher`), além de `login()` / `refresh()` (rotação single-use) / `logout()` (idempotente) em `IdentityService`. Nenhum comportamento de endpoint mudou — continua sem nenhuma rota `/auth/*` ou comando CLI expostos; isso é Fase 3.

> **Atualização v0.1.10:** Fase 3 de Identidade e Controle de Acesso implementada — a fase que finalmente muda comportamento em runtime. Três rotas novas, `POST /auth/login` / `POST /auth/refresh` / `POST /auth/logout` (seção 11), mais os comandos `orchai auth login` / `orchai auth logout` / `orchai auth bootstrap-admin`. Toda rota pré-existente (50 das 54 rotas da aplicação, fora as 3 novas de `/auth/*` e as 4 de docs/openapi) e todo comando CLI pré-existente (46 dos 49 comandos — só `auth login`, `auth bootstrap-admin` e `api serve` ficam de fora, o primeiro e o segundo por serem o próprio caminho de bootstrap, e `api serve` por não ter uma rota HTTP correspondente) agora passa por uma checagem de permissão declarativa — `require_permission(key)` (dependency do FastAPI) e `require_cli_permission(key)` (chamada explícita no início do corpo do comando, não decorator, para não quebrar a introspecção de assinatura do Typer/Click) — mas essa checagem é **inerte por padrão**: `ORCHAI_AUTH_ENFORCED=false` é o padrão de rollout (`docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §6), então nenhum comportamento de nenhum endpoint/comando pré-existente mudou para quem não ligar a flag. Com a flag ligada, um bearer token JWT válido passa a ser exigido (401 se ausente/inválido), e a permissão específica de cada rota/comando passa a ser exigida (403 se ausente) — superusuários (`is_superuser`) sempre passam. Ver seção 11 para a lista completa de rotas de autenticação e `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §4 para o mapeamento completo de permissões. Suíte agora com **178 testes**.

> **Atualização v0.1.11:** Fase 4 de Identidade e Controle de Acesso implementada — a camada de CRUD de configuração de usuários pedida explicitamente pelo usuário como pré-requisito antes de partir para a "refatoração para usuários" mais ampla. Sete rotas novas: `GET`/`POST /admin/users`, `PUT /admin/users/{id}/access-roles`, `GET`/`POST /admin/access-roles`, `PUT /admin/access-roles/{id}/permissions`, `GET /admin/projects` (seção 12), mais `GET`/`PATCH /me` e `GET /me/projects` (também seção 12). Comandos CLI equivalentes: `orchai users list|create|set-access-roles`, `orchai access-roles list|create|set-permissions`, `orchai projects list-all`, `orchai me show|update|projects`. O modelo `AccessRole` N:N (Fase 1) não mudou em nada — em vez disso, criar um usuário não-superusuário agora exige informar ao menos um `AccessRoleId` (substituindo um design anterior de "AccessRole Padrão do sistema" que o usuário pediu para simplificar). Uma nova tabela puramente informativa, `project_connections` (migração `0008_project_connections.sql`), registra qual usuário conectou qual projeto — **não** é um limite de controle de acesso. `POST /projects` passou a vincular automaticamente o usuário autenticado quando há um token válido, mudança feita capturando o retorno de `require_permission` em vez de descartá-lo — a única alteração de comportamento em uma rota pré-existente nesta fase, e mesmo assim não muda a checagem de permissão nem o formato de resposta para quem já usava a rota. Esta fase também corrigiu uma lacuna latente: `permissions`/`access_roles` começavam vazias num banco novo, sem nenhum seeding em lugar nenhum do código — hoje o catálogo completo de permissões é semeado automaticamente e de forma idempotente a cada construção do identity runtime. Ver `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §8 para o design completo. Suíte agora com **203 testes**.

Legenda de status:

- **✅ Completo** — funciona fim a fim como documentado, coberto por teste de integração.
- **⚠️ Parcial** — o endpoint responde e faz algo real, mas não cobre todo o comportamento que o nome sugere (detalhado na coluna de ações).
- **🚧 Não implementado** — não existe endpoint algum; mencionado aqui só para deixar explícito o que falta.

A API é dividida em duas superfícies (ADR-011): `/requests/*` é a superfície **chat-first**, pensada como ponto de entrada principal para clientes externos (chat UIs, apps). Os demais grupos (`/tasks`, `/authorizations`, `/executions`, etc.) são a superfície **operacional**, de controle fino — usada tanto por operadores/scripts quanto internamente pela própria superfície chat-first.

---

## 1. Sistema e Providers

| Endpoint | Status | Papel no fluxo | O que faz concretamente |
|---|---|---|---|
| `GET /` | ✅ | Índice da API | Lista os pontos de entrada principais e o dialeto de banco recomendado (postgresql). Não toca banco de dados. |
| `GET /health` | ✅ | Health check simples | Retorna `{"status": "ok", "version": "0.1.11"}`. Não valida banco nem provider. |
| `GET /settings/runtime` | ✅ | Diagnóstico de configuração | Mostra a configuração efetiva resolvida (banco, provider de IA, host/porta da API) — útil para confirmar qual banco/URL está realmente em uso antes de operar. |
| `GET /runtime/check` | ✅ | Diagnóstico consolidado | Testa conectividade real com o banco (`SELECT 1`) e healthcheck do provider de IA configurado, retornando `ready: true/false` e avisos (`warnings`) quando algo não está pronto para produção. |
| `GET /providers/settings` | ✅ | Configuração do provider de IA | Mostra qual provider está configurado (`stub`, `ollama`, `openai`), modelo, timeout, se a API key está presente — sem expor a chave em si. |
| `GET /providers/capabilities` | ✅ | Capacidades declaradas | Lista as capacidades que o provider afirma suportar (ex: `read_project`, `write_source`). Hoje só o provider `stub` está implementado de fato; `ollama`/`openai` existem como adapters mas ainda não foram plugados como opção real de execução (é exatamente o próximo passo). |
| `GET /providers/health` | ✅ | Healthcheck do provider | Faz uma checagem de alcançabilidade real contra o provider configurado. |

## 2. Administração de Banco

| Endpoint | Status | Papel no fluxo | O que faz concretamente |
|---|---|---|---|
| `POST /admin/db/sync` | ✅ | **Única operação de administração de banco** | Desde v0.1.7, é o único endpoint de administração de banco — `POST /admin/db/create` e `POST /admin/db/migrate` foram removidos. Cria o banco se necessário (só tem efeito real em PostgreSQL, via `CREATE DATABASE`, validando antes se já existe) e em seguida aplica as migrações SQL versionadas incondicionalmente (`infrastructure/persistence/db/migrations/*.sql`, idempotente, registra versão em `schema_migrations`). Em SQLite/local-flow o passo de criação é apenas pulado — `create_status: "skipped_non_postgresql"`, com uma mensagem explícita de que a operação não se aplica ao banco/local-flow selecionado — **sem erro**; as migrações são aplicadas normalmente. Equivalente ao comando CLI `orchai db sync`, que tem o mesmo comportamento informativo (não gera erro/exit code != 0 para SQLite). |

## 3. Projetos

| Endpoint | Status | Papel no fluxo | O que faz concretamente |
|---|---|---|---|
| `GET /projects/discover` | ✅ | Exploração pontual (sem persistir) | Varre um diretório local e lista recursos (arquivos) classificados, sem gravar nada no banco. Útil para "olhar antes de conectar". |
| `GET /projects/readiness` | ✅ | Avaliação pontual (sem persistir) | Avalia o nível de prontidão de um diretório (`LEVEL_0`..`LEVEL_3`, baseado em ter `.git`, testes, CI) sem persistir. |
| `GET /projects/security` | ✅ | Avaliação pontual (sem persistir) | Deriva o perfil de segurança observado (o que pode ser lido/persistido/compartilhado com provider) a partir do disco, sem persistir. |
| `POST /projects` | ✅ | **Conectar um projeto** | Este é o passo que efetivamente registra o projeto: avalia prontidão/segurança do diretório e persiste um registro de `Project` no banco, retornando `project_id`. É o ponto de partida real de qualquer fluxo. |
| `GET /projects` | ✅ | Listar projetos conectados | Lista projetos já registrados no banco. |
| `GET /projects/lookup` | ✅ | Encontrar projeto por caminho | Busca um projeto já registrado pelo `project_root`, evitando registrar duplicado. |
| `GET /projects/{project_id}` | ✅ | Detalhe de um projeto | Retorna o registro persistido, incluindo níveis de prontidão/segurança efetivos vs. observados. |
| `PATCH /projects/{project_id}/security` | ✅ | Ajustar política de segurança | Permite elevar/restringir manualmente o perfil de segurança efetivo de um projeto (ex: liberar compartilhamento com provider de nuvem), independente do que foi observado no disco. |

## 4. Tarefas (Tasks)

| Endpoint | Status | Papel no fluxo | O que faz concretamente |
|---|---|---|---|
| `POST /tasks` | ✅ | Criar uma tarefa | Cria uma `Task` vinculada a um projeto, em estado `CREATED`, com o `execution_mode` desejado (`MANUAL`/`SUGGESTED`/`AUTOMATIC`). |
| `GET /tasks` | ✅ | Listar tarefas | Lista com filtro por projeto e estado. |
| `GET /tasks/{task_id}` | ✅ | Detalhe de uma tarefa | Estado atual + transições disponíveis a partir dali (máquina de estados). |
| `GET /tasks/{task_id}/snapshot` | ✅ | Visão consolidada | Junta autorizações, execuções, sugestões, eventos, auditoria e métricas de uma tarefa em uma única resposta — é a base do `GET /requests/{id}/flow`. |
| `POST /tasks/{task_id}/transition` | ✅ | Transição manual de estado | Move a tarefa para outro estado da máquina de estados diretamente (uso operacional/administrativo, não passa por sugestão nem autorização). |
| `POST /tasks/{task_id}/advance` | ✅ | **Avançar um estágio do workflow** | Este é o motor real do fluxo: PLAN → IMPLEMENT → REVIEW → VALIDATE → TEST → DOCUMENT. Cada chamada resolve automaticamente qual é o próximo estágio (via `SuggestionEngine`), avalia política, e se `approve_stage: true`, solicita+concede autorização e executa a etapa via o provider de IA configurado. |

## 5. Políticas

| Endpoint | Status | Papel no fluxo | O que faz concretamente |
|---|---|---|---|
| `POST /policies/evaluate` | ✅ | Simular uma decisão de política | Avalia se uma operação seria permitida (sem executar nada), útil para debug/dry-run. **Importante:** isto é só avaliação — não existe endpoint para *configurar* os limites da política em runtime (ver seção "Lacunas conhecidas" abaixo). |

## 6. Autorizações

| Endpoint | Status | Papel no fluxo | O que faz concretamente |
|---|---|---|---|
| `POST /authorizations/request` | ✅ | Solicitar autorização | Cria um registro de autorização pendente (sem decisão) para um `role`+`action` sobre uma tarefa. |
| `POST /authorizations/{id}/decision` | ✅ | Decidir uma autorização | Grava uma decisão explícita (`GRANTED`/`REJECTED`/`EXPIRED`/`REVOKED`). É o único jeito de uma autorização deixar de estar "pendente". |
| `GET /authorizations` | ✅ | Listar/filtrar autorizações | Suporta filtro por `task_id`, `status` e `pending_only` (adicionado nesta sessão — antes só filtrava por `task_id`). |
| `GET /authorizations/{id}` | ✅ | Detalhe de uma autorização | Estado, decisão mais recente, escopo de contexto solicitado. |

## 7. Execuções

| Endpoint | Status | Papel no fluxo | O que faz concretamente |
|---|---|---|---|
| `POST /executions/request` | ✅ | Criar uma execução autorizada | Vincula uma execução a uma autorização já concedida — não roda nada ainda. |
| `POST /executions/{id}/run` | ✅ | **Executar de forma síncrona** | Roda a execução até o fim (chama o provider de IA, resolve resultado) e só responde quando termina. |
| `POST /executions/{id}/dispatch` | ✅ | **Executar de forma assíncrona** | Agenda a execução como uma tarefa asyncio em background e responde imediatamente com `dispatched: true`; o cliente consulta `GET /executions/{id}` depois para ver quando chega a `COMPLETED`. Validado com teste de polling. |
| `POST /executions/{id}/transition` | ✅ | Transição manual de estado | Move a execução manualmente entre estados (`PREPARING`, `STARTED`, `RUNNING`, etc.) — uso operacional/debug. |
| `POST /executions/{id}/complete` | ✅ | Registrar resultado manualmente | Fecha uma execução com resultado/erros/uso de recursos explícitos, sem passar pelo provider de IA — usado por integrações externas ou testes. |
| `POST /executions/{id}/resolve-context` | ✅ | Resolver contexto autorizado | Materializa o conteúdo dos arquivos autorizados (ex: lê o `README.md` do disco) e persiste um registro de resolução. |
| `GET /executions/{id}/context` | ✅ | Ver contexto já resolvido | Lista os registros de resolução de contexto de uma execução. |
| `GET /executions` / `GET /executions/{id}` | ✅ | Listar/detalhar execuções | Com filtro por tarefa, projeto e estado. |
| — (cancelamento) | 🚧 | — | **Não existe.** Há um método `cancel()` declarado na interface (`ExecutionRepository` port) mas nenhuma classe o implementa e nenhum endpoint o chama. Tecnicamente dá para forçar `POST /executions/{id}/transition` com `target_state: CANCELLED` (a máquina de estados aceita esse alvo), mas isso só troca o status no banco — **não interrompe** uma execução já despachada em background via `dispatch`. |

## 8. Observabilidade (Auditoria, Métricas, Eventos, Sugestões)

| Endpoint | Status | Papel no fluxo | O que faz concretamente |
|---|---|---|---|
| `GET /audit` | ✅ | Trilha de auditoria | Lista registros de auditoria (quem fez o quê, quando, com qual resultado), gerados automaticamente a cada evento de domínio relevante. Agora inclui `correlation_id`/`causation_id`. |
| `GET /audit/{id}` | ✅ | Detalhe de um registro | Adicionado nesta sessão. |
| `GET /events` | ✅ | Histórico de eventos de domínio | Lista eventos brutos (`TASK_CREATED`, `EXECUTION_COMPLETED`, etc.), com filtro por tipo/tarefa/execução/projeto. |
| `GET /metrics` | ⚠️ | Registros de métricas brutos | Lista registros individuais gerados automaticamente por execução (ex: `execution.success`, tokens, custo). **Não há agregação** — nenhum endpoint calcula soma/média/taxa de sucesso ao longo do tempo; quem quiser um dashboard precisa agregar do lado do cliente com os registros brutos. |
| — (agregação de métricas) | 🚧 | — | **Não existe.** O `MetricsRepository` só tem `add_many`/`list` — nenhum método de agregação, nem no domínio nem na infraestrutura. |
| `GET /suggestions` | ✅ | Listar sugestões | Com filtro por tarefa. |
| `GET /suggestions/{id}` | ✅ | Detalhe de uma sugestão | Adicionado nesta sessão. |
| `POST /tasks/{task_id}/suggestions` | ✅ | Gerar sugestão sob demanda | Adicionado nesta sessão — antes só era gerada automaticamente dentro do `advance`/`local-flow`. |
| `POST /suggestions/{id}/accept` | ✅ | Aceitar uma sugestão | Adicionado nesta sessão. Importante: isso só marca o registro como `ACCEPTED` — **não** dispara autorização nem execução por si só (isso continua acontecendo apenas dentro do `advance`, ver nota na seção 9). |
| `POST /suggestions/{id}/reject` | ✅ | Rejeitar uma sugestão | Adicionado nesta sessão. |

## 9. Superfície Chat-First (`/requests/*`) — entrada principal

| Endpoint | Status | Papel no fluxo | O que faz concretamente |
|---|---|---|---|
| `POST /requests` | ✅ | **Criar um pedido em linguagem natural** | Recebe `project_root` + `prompt` (+ opcionalmente `role`/`action`/`model`). Registra o projeto (idempotente, por `root_location`), cria a tarefa e avança por **exatamente um estágio gated** — PLAN, o primeiro. Corrigido nesta sessão: antes, o estágio PLAN acontecia de forma síncrona e sem gate nenhum, e a primeira sugestão que o cliente via já era `IMPLEMENT` (task já em `PLANNED`) — um desvio real do que a documentação especifica, não uma nuance. Hoje a primeira sugestão é sempre `PLAN`/`TASK_PLANNER`, avaliada pela mesma política de qualquer outro estágio: em modo `SUGGESTED` (padrão) sem `approve_suggestion: true`, a chamada para em `PLANNING` com a sugestão `PRESENTED` e `blocked_reason: "suggested_mode_requires_approval"` — nenhuma autorização é criada. Com `approve_suggestion: true`, o estágio PLAN roda de verdade (autorização concedida + execução) e a tarefa para em `PLANNED`, pronta para o próximo `advance`. Confirmado empiricamente (não só por leitura de código) rodando a chamada de verdade. |
| `GET /requests/{id}/flow` | ✅ | **Observar o estado completo** | Visão unificada (tarefa + autorizações + execuções + sugestões + auditoria + métricas), com um campo `status` derivado (`PENDING_SUGGESTION`, `PENDING_AUTHORIZATION`, `RUNNING`, `COMPLETED`, etc.) — corrigido nesta sessão (ver nota abaixo). |
| `POST /requests/{id}/approve` | ✅ | **Aprovar e continuar, cobrindo os dois casos possíveis** | Reavaliado e corrigido em v0.1.6. Cobre dois casos: (1) já existe uma autorização pendente/não-decidida (ex: criada por fora via `POST /authorizations/request` direto contra a tarefa) — é concedida diretamente, como antes; (2) o caso comum em modo `SUGGESTED`, onde `run_task_workflow_stage` retorna antes de criar qualquer autorização quando a política bloqueia, deixando só a sugestão `PRESENTED` — agora, se não houver autorização pendente mas houver uma sugestão `PRESENTED`, `/approve` delega internamente para o mesmo mecanismo gated de `/advance` (`approve_stage: true`). Não é um bypass: a chamada delegada ainda passa pela mesma avaliação de política, e se ela recusar (ex: modo/config mudou), a resposta volta com `blocked_reason` preenchido e `approved: false`, exatamente como `/advance` reportaria. Como consequência, `/approve` aceita opcionalmente os mesmos campos de contexto que `/advance` (`context_paths`, `documentation_path`, `test_args`, `model`, `provider_target`) — necessários apenas quando o estágio atual os exige (ex: PLAN exige `context_paths`); são ignorados quando o caso (1) se aplica. |
| `POST /requests/{id}/advance` | ✅ | **Avançar para o próximo estágio** | Equivalente chat-first de `POST /tasks/{task_id}/advance` — é este endpoint, chamado com `approve_stage: true`, que efetivamente faz a tarefa progredir (PLAN → IMPLEMENT → REVIEW → ...), concedendo autorização e executando via o provider configurado. |

## 10. Fluxos legados (mantidos por compatibilidade)

| Endpoint | Status | Papel no fluxo | O que faz concretamente |
|---|---|---|---|
| `POST /flows/local` | ✅ | Fluxo local de demonstração | Precursor do `/requests` — usa exatamente o mesmo mecanismo interno (`run_local_flow`), então herda a mesma correção: cria projeto+tarefa e avança só o primeiro estágio gated (PLAN), não pula direto para uma execução completa. Mantido por compatibilidade. |
| `POST /projects/operations` | ✅ | Operação protegida no projeto | Executa uma operação específica no Project Adapter (ler, escrever, rodar comando/teste) via política+autorização, fora do ciclo PLAN→...→DOCUMENT. A tarefa criada aqui ainda precisa passar por `PLANNED` antes de iniciar a operação (exigência mecânica da máquina de estados) — esse hop também foi corrigido nesta sessão para passar pelo mesmo gate de sugestão/política (papel `TASK_PLANNER`/ação `PLAN`), em vez de acontecer sem nenhum registro. Um único `approve_operation: true` cobre tanto esse bootstrap quanto a operação em si. |

---

## 11. Autenticação (ADR-012, Fase 3)

| Endpoint | Status | Papel no fluxo | O que faz concretamente |
|---|---|---|---|
| `POST /auth/login` | ✅ | **Autenticar** | Troca `username`/`password` por um par access/refresh token. `401` para credenciais inválidas ou usuário inativo. Não exige autenticação prévia — é o ponto de entrada. Equivalente CLI: `orchai auth login`, que persiste o par de tokens em `~/.orchai/credentials.json` (permissão `0600`). |
| `POST /auth/refresh` | ✅ | **Renovar sessão** | Troca um refresh token válido por um novo par access/refresh (rotação single-use — o token usado é invalidado no mesmo passo). `401` para token ausente, expirado, inválido ou já usado. |
| `POST /auth/logout` | ✅ | **Encerrar sessão** | Revoga um refresh token (idempotente — chamar de novo não é erro). Exige autenticação (qualquer usuário válido), sem permissão específica. Equivalente CLI: `orchai auth logout`, que também limpa `~/.orchai/credentials.json`. |
| `orchai auth bootstrap-admin` | ✅ | **Criar o primeiro superusuário** | Sem rota HTTP equivalente (ADR-012 §8) — resolve o problema do ovo e da galinha: só funciona enquanto existir zero usuários no banco, sem exigir um chamador já autenticado. Username/senha vêm de `--username`/`--password` ou de `ORCHAI_ADMIN_USERNAME`/`ORCHAI_ADMIN_PASSWORD`. |

Todas as demais rotas e comandos pré-existentes passaram a declarar uma permissão exigida (`require_permission(key)` / `require_cli_permission(key)`), mas essa checagem só é aplicada de fato quando `ORCHAI_AUTH_ENFORCED=true` — o padrão é `false` (inerte), preservando o comportamento de toda rota/comando documentado nas seções 1 a 10 acima para quem ainda não ligou a flag. O mapeamento completo de permissão por rota/comando está em `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §4, não duplicado aqui. Um token de superusuário (`is_superuser`) sempre satisfaz qualquer permissão.

A gestão de usuários ganhou uma superfície própria na Fase 4 (seção 12) — `admin:manage_users` já não é uma permissão sem consumidor.

---

## 12. Configuração de Usuários — Admin e Self-Service (ADR-012, Fase 4)

| Endpoint | Status | Papel no fluxo | O que faz concretamente |
|---|---|---|---|
| `GET /admin/users` | ✅ | **Listar todos os usuários** | Retorna todos os campos de cada usuário (username, email, is_superuser, is_active, timestamps, `access_roles` resolvidos por nome, `connected_project_ids`) — exceto `password_hash`, nunca exposto. Exige `admin:manage_users`. |
| `POST /admin/users` | ✅ | **Criar um novo usuário** | Cria o usuário e já atribui seus `AccessRole`s iniciais (`role_ids`). Um usuário não-superusuário sem nenhum `role_id` é rejeitado com `400` (`UserRequiresAccessRoleError`) — substitui o design de "AccessRole Padrão do sistema" descartado pelo usuário por uma regra mais simples com a mesma garantia prática. Username duplicado → `409`. Exige `admin:manage_users`. |
| `PUT /admin/users/{id}/access-roles` | ✅ | **Substituir os `AccessRole`s de um usuário** | Operação *replace-all*, não incremental: a lista enviada vira o conjunto completo. Esvaziar para zero é rejeitado (`400`) a menos que o usuário seja superusuário. Exige `admin:manage_users`. |
| `GET /admin/access-roles` | ✅ | **Listar todos os `AccessRole`** | Cada item vem com `permissions` e `users` totalmente resolvidos (não apenas ids). Exige `admin:manage_users`. |
| `POST /admin/access-roles` | ✅ | **Criar um `AccessRole`** | Nome duplicado → `409`. Reutiliza `IdentityService.create_access_role`, já testado desde a Fase 1. Exige `admin:manage_users`. |
| `PUT /admin/access-roles/{id}/permissions` | ✅ | **Substituir o bundle de permissões de um `AccessRole`** | Também *replace-all*. `Permission` continua sendo um catálogo fixo do sistema — não há endpoint para criar novas permissões, só para (re)atribuí-las a um `AccessRole`. Exige `admin:manage_users`. |
| `GET /admin/projects` | ✅ | **Diretório administrativo de projetos** | Lista todo projeto do sistema com `capabilities`, níveis de prontidão e `connected_user_ids` — diferente de `GET /projects` (`projects:read`), que lista projetos mas sem esses detalhes administrativos. Exige a nova permissão `admin:manage_projects`. |
| `GET /me` | ✅ | **Ver o próprio perfil** | Retorna os mesmos campos de `GET /admin/users` para o usuário autenticado, incluindo `access_roles` e `connected_project_ids`. |
| `PATCH /me` | ✅ | **Atualizar o próprio perfil** | Só aceita `username`/`email` — não existe campo para o usuário alterar seu próprio `AccessRole` ou `is_superuser`. Username duplicado → `409`. |
| `GET /me/projects` | ✅ | **Projetos conectados pelo usuário logado** | Lê de `project_connections` (ver nota abaixo). |

**Importante sobre `/me`:** essas três rotas não usam `require_permission()` (que vira um no-op quando `ORCHAI_AUTH_ENFORCED=false`, deixando "qual é o usuário atual" indefinido). Usam uma dependency própria, `require_authenticated_user()` (`require_authenticated_cli_user()` no CLI), que **sempre** exige um bearer token válido, independente da flag — não existe uma leitura sensata de "no-op" para "mostrar meu próprio perfil".

**`project_connections` não é controle de acesso.** É uma referência puramente informativa — "este usuário conectou este projeto ao OrchAI" — que não restringe leitura, registro nem operação sobre nenhum projeto, e um projeto pode ser conectado por vários usuários. `POST /projects` agora vincula automaticamente o chamador autenticado (quando há um token válido) a esse registro. Vive no mesmo banco de `projects` (não no banco de identidade, que fica fixo por segurança), já que é metadado descritivo do projeto, não um dado de identidade.

---

## Lacunas conhecidas (confirmadas por leitura de código, não suposição)

1. **Cancelamento de execução** — não existe de fato. O port declara `cancel()`, nada implementa. `target_state: CANCELLED` via transição manual só troca o status no banco, não para nada em background.
2. **Agregação de métricas** — só existe listagem de registros brutos por execução; nenhuma soma/média/taxa ao longo do tempo ou por projeto.
3. **Configuração runtime de `AutomaticExecutionPolicy`** — zero exposição na CLI ou na API. Os limites do modo `AUTOMATIC` (quais `role`+`action` são permitidos automaticamente, se pode trocar de modelo, se pode expandir contexto) são hoje só o valor padrão hardcoded no código (`allowed_operations=((DEVELOPER, IMPLEMENT),)`); não há como um usuário configurar isso sem editar o código-fonte. **Isso ficou mais visível com a correção do gate de PLAN na v0.1.5:** como PLAN agora também exige estar na allowlist do `AutomaticExecutionPolicy` para pular aprovação, e `(TASK_PLANNER, PLAN)` não está na allowlist padrão, hoje **nenhum** pedido em modo `AUTOMATIC` via CLI/API consegue passar do primeiro estágio sem essa configuração — o modo `AUTOMATIC` só funciona de fato através da API Python interna (`RunLocalFlowCommand`/`RunProjectOperationCommand` com `automatic_policy` customizado), não pela CLI/API pública. Isso não é uma regressão da correção — é a política corretamente aplicada revelando uma lacuna que já existia (a config nunca esteve exposta); mas antes da correção passava despercebida porque o próprio PLAN não era avaliado.
4. **`ORCHAI_AUTH_ENFORCED` ainda é `false` por padrão** (seção 11) — a checagem de permissão existe em toda rota/comando, mas está inerte até essa flag ser ligada deliberadamente (rollout intencional, `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §6, não um bug). Sem ela ligada, a API/CLI continuam abertas exatamente como antes da Fase 3.

**Resolvidas** (mantidas aqui por rastreabilidade):

- ~~`/requests/{id}/approve` não resolve o caso comum de `PENDING_SUGGESTION`~~ (v0.1.6) — corrigido: ver seção 9. `/approve` agora delega para o mesmo mecanismo gated de `/advance` quando só existe uma sugestão `PRESENTED`.
- ~~`POST /admin/db/create` gerava um erro forte na CLI (`typer.BadParameter`) para banco não-PostgreSQL, mas retornava uma resposta informativa 200 na API para o mesmo caso~~ (v0.1.7) — em vez de alinhar os dois, `db create` e `db migrate` foram **removidos**; `db sync`/`POST /admin/db/sync` é agora a única operação de administração de banco, cobrindo os dois casos num só passo — ver seção 2.
- ~~Gestão de usuários não tinha superfície própria~~ (v0.1.11) — resolvido pela Fase 4: ver seção 12. `orchai users *` / `orchai access-roles *` / `GET,POST /admin/users` / `GET,POST /admin/access-roles` agora existem e consomem `admin:manage_users`.

---

## Exemplo de uso completo via API

Cenário: conectar um projeto, criar um pedido, avançar até a etapa de **review de código**. Toda a sequência abaixo foi **rodada de verdade** contra a API (via `TestClient`, não apenas inferida do código) para garantir que o exemplo reflete o comportamento real — já com a correção do gate de PLAN aplicada nesta sessão (ver a nota de atualização no topo deste documento).

```bash
BASE=http://localhost:8000
DB="sqlite:///./demo.db"   # ou omita para usar o PostgreSQL padrão

# 1. Conectar (registrar) o projeto — opcional como passo isolado, já que o
#    /requests do passo 2 registra o projeto sozinho (upsert por caminho),
#    mas fazer aqui deixa o project_id disponível para filtros depois.
curl -s -X POST "$BASE/projects" -H 'Content-Type: application/json' -d '{
  "project_root": "/caminho/do/seu/projeto",
  "database_url": "'"$DB"'"
}'
# → { "project_id": "…", "readiness_level": "LEVEL_2_VALIDATABLE", ... }

# 2. Criar o pedido em linguagem natural (chat-first)
curl -s -X POST "$BASE/requests" -H 'Content-Type: application/json' -d '{
  "project_root": "/caminho/do/seu/projeto",
  "prompt": "Implementar validação de e-mail no cadastro de usuários",
  "context_paths": ["src/cadastro.py"],
  "database_url": "'"$DB"'"
}'
# → { "request_id": "…", "status": "PENDING_SUGGESTION",
#     "suggestion": { "suggested_role": "TASK_PLANNER", "suggested_action": "PLAN", ... } }
REQUEST_ID="…"   # copie o request_id retornado
```

A primeira sugestão agora é sempre `PLAN`/`TASK_PLANNER`, exatamente como `docs/architecture/CHAT-FIRST-REQUEST-MODEL.md` (seção 3) descreve — "o próximo passo depois de conectar" é mesmo planejar, não implementar. A tarefa fica em `PLANNING`, aguardando aprovação como qualquer outro estágio.

```bash
# 3. Avançar para PLAN, aprovando explicitamente — este estágio agora roda
#    de verdade (autorização + execução), como qualquer outro
curl -s -X POST "$BASE/requests/$REQUEST_ID/advance" -H 'Content-Type: application/json' -d '{
  "context_paths": ["src/cadastro.py"],
  "approve_stage": true,
  "database_url": "'"$DB"'"
}'
# → { "stage": "PLAN", "task_state": "PLANNED", "execution_state": "COMPLETED",
#     "output": "Stub provider processed 1 authorized context item(s)." }

# 4. Avançar para IMPLEMENT
curl -s -X POST "$BASE/requests/$REQUEST_ID/advance" -H 'Content-Type: application/json' -d '{
  "context_paths": ["src/cadastro.py"],
  "approve_stage": true,
  "database_url": "'"$DB"'"
}'
# → { "stage": "IMPLEMENT", "task_state": "IMPLEMENTED", "execution_state": "COMPLETED",
#     "output": "Stub provider processed 1 authorized context item(s)." }

# 5. Avançar para REVIEW — a etapa de revisão de código que você pediu
curl -s -X POST "$BASE/requests/$REQUEST_ID/advance" -H 'Content-Type: application/json' -d '{
  "context_paths": ["src/cadastro.py"],
  "approve_stage": true,
  "database_url": "'"$DB"'"
}'
# → { "stage": "REVIEW", "task_state": "REVIEWING", "execution_state": "COMPLETED",
#     "output": "Stub provider processed 1 authorized context item(s)." }

# 6. A qualquer momento, ver o estado completo do pedido
curl -s "$BASE/requests/$REQUEST_ID/flow?database_url=$DB"
# → task (state=REVIEWING), autorizações, execuções, sugestões, auditoria e
#   métricas, tudo junto. Uma nova sugestão (para VALIDATE) já aparece aqui,
#   marcada PRESENTED, porque a próxima etapa também requer aprovação.
```

Observações sobre o exemplo:

- Cada chamada a `/advance` resolve sozinha qual é o próximo estágio (via a `SuggestionEngine`) — não é preciso informar `stage` explicitamente, a menos que você queira forçar uma etapa específica fora de ordem.
- `approve_stage: true` é o que efetivamente autoriza e executa a etapa, **para qualquer estágio, inclusive PLAN**. Sem ele, a chamada para no estado `blocked_reason: "suggested_mode_requires_approval"`, sem criar autorização nenhuma (a tarefa fica em `PLANNING`, nem chega a `PLANNED`). A partir da v0.1.6, `POST /requests/{id}/approve` também resolve esse caso — chamá-lo (passando `context_paths` quando o estágio bloqueado exigir contexto, como PLAN) tem o mesmo efeito que repetir o `/advance` com `approve_stage: true`.
- Se você tentar avançar mais uma vez depois do passo 5 (rumo a `VALIDATE`), a chamada tende a bloquear com `blocked_reason: "validation_requires_level_2"` a menos que o projeto conectado já tenha estrutura de testes reconhecida no disco (nível de prontidão `LEVEL_2_VALIDATABLE`) — é a política de prontidão do projeto, não um bug, mas vale saber antes de montar um fluxo automatizado ponta a ponta.
- O `"output": "Stub provider processed …"` reflete que hoje a execução roda contra o provider `stub` (determinístico, sem custo, sem IA real) — é exatamente esse ponto que os adapters reais de Ollama/OpenAI/Anthropic vão substituir.
