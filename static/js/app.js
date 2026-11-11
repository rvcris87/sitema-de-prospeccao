document.addEventListener("DOMContentLoaded", () => {
    // -------------------------------------------------------------
    // 1. CRM Dynamic Status Updates
    // -------------------------------------------------------------
    // Delegado no document: vale para a tabela, o painel lateral e linhas inseridas via fetch.
    document.addEventListener("change", async (event) => {
        const select = event.target.closest(".crm-status-select");
        if (!select) return;
        const leadId = select.dataset.leadId;
        const newStatus = select.value;
        const savedOption = [...select.options].find(option => option.defaultSelected);
        const oldStatus = savedOption ? savedOption.value : null;

        select.disabled = true;
        try {
            const response = await fetch(`/api/leads/${leadId}/status`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status: newStatus })
            });
            const result = await response.json();

            if (response.ok && result.ok) {
                // Troca só a linha deste lead e sincroniza o outro select (tabela <-> painel).
                if (result.html) replaceLeadRow(leadId, result.html);
                document.querySelectorAll(`.crm-status-select[data-lead-id="${leadId}"]`).forEach(other => {
                    [...other.options].forEach(option => {
                        option.defaultSelected = option.value === newStatus;
                    });
                    other.value = newStatus;
                });
                if (leadsPage) leadsPage.onStatusChanged(oldStatus, newStatus);
                showToast(`Status atualizado para: ${newStatus}`);
            } else {
                if (oldStatus !== null) select.value = oldStatus;
                showToast("Erro ao atualizar status.", "error");
            }
        } catch (error) {
            if (oldStatus !== null) select.value = oldStatus;
            showToast("Erro de comunicação com o servidor.", "error");
        } finally {
            select.disabled = false;
        }
    });

    // Um lead pode aparecer em mais de uma tabela na mesma página (ex.: Dashboard).
    function findLeadRows(leadId) {
        return [...document.querySelectorAll(`.lv-table tr.lead-row[data-lead-id="${leadId}"]`)];
    }

    function findLeadRow(leadId) {
        return findLeadRows(leadId)[0] || null;
    }

    function replaceLeadRow(leadId, html) {
        const template = document.createElement("template");
        template.innerHTML = html.trim();
        const source = template.content.querySelector("tr.lead-row");
        if (!source) return;
        findLeadRows(leadId).forEach(row => {
            const newRow = source.cloneNode(true);
            if (row.classList.contains("is-sel")) newRow.classList.add("is-sel");
            row.replaceWith(newRow);
        });
    }

    // -------------------------------------------------------------
    // 1b. Tabelas de leads: painel lateral (qualquer página com #leadDrawer)
    //     e, na tela de Leads, filtros sem recarregar e chips de status
    // -------------------------------------------------------------
    const leadsPage = setupLeadsPage();

    function setupLeadsPage() {
        const drawer = document.getElementById("leadDrawer");
        if (!drawer) return null;
        const form = document.getElementById("leadsFilterForm");
        const tableBody = document.getElementById("leadsTableBody");

        const statusSelect = form?.querySelector('select[name="status"]');
        const searchInput = form?.querySelector('input[name="q"]');
        const chipsContainer = document.getElementById("leadsStatusChips");
        const statusOrder = statusSelect ? [...statusSelect.options].map(option => option.value).filter(Boolean) : [];
        let counts = {};
        try {
            counts = JSON.parse(document.getElementById("leadsInitialCounts")?.textContent || "{}");
        } catch (error) {
            counts = {};
        }

        // ---------- Filtros (só na tela de Leads) ----------
        if (form && tableBody) setupFilters();

        function setupFilters() {
            let filterRequestId = 0;
            let searchTimer = null;

            const applyFilters = async () => {
                const params = new URLSearchParams();
                new FormData(form).forEach((value, key) => {
                    if (String(value).trim() !== "") params.set(key, String(value).trim());
                });
                const query = params.toString();
                // Mantém os filtros na URL para que F5 preserve o resultado.
                history.replaceState(null, "", query ? `${location.pathname}?${query}` : location.pathname);
                renderChips();

                const requestId = ++filterRequestId;
                tableBody.classList.add("is-loading");
                try {
                    const response = await fetch(`${form.dataset.apiUrl}?${query}`, {
                        headers: { "Accept": "application/json" }
                    });
                    const result = await response.json();
                    // Ignora respostas antigas se o usuário trocou o filtro de novo.
                    if (requestId !== filterRequestId) return;
                    if (response.ok && result.ok) {
                        tableBody.innerHTML = result.html;
                        counts = result.contagens || counts;
                        renderChips();
                        markActiveRow();
                    } else {
                        showToast("Erro ao filtrar leads.", "error");
                    }
                } catch (error) {
                    if (requestId === filterRequestId) showToast("Erro de comunicação com o servidor.", "error");
                } finally {
                    if (requestId === filterRequestId) tableBody.classList.remove("is-loading");
                }
            };

            form.addEventListener("submit", (event) => {
                event.preventDefault();
                applyFilters();
            });
            form.addEventListener("change", (event) => {
                if (event.target === searchInput) return; // a busca já filtra pelo "input"
                applyFilters();
            });
            searchInput?.addEventListener("input", () => {
                clearTimeout(searchTimer);
                searchTimer = setTimeout(applyFilters, 300);
            });

            form.querySelector("[data-clear-filters]")?.addEventListener("click", (event) => {
                event.preventDefault();
                form.querySelectorAll("select").forEach(select => { select.value = ""; });
                if (searchInput) searchInput.value = "";
                applyFilters();
            });

            chipsContainer?.addEventListener("click", (event) => {
                const chip = event.target.closest(".lv-chip");
                if (!chip) return;
                statusSelect.value = chip.dataset.status === statusSelect.value ? "" : chip.dataset.status;
                applyFilters();
            });
        }

        // ---------- Chips de contagem por status ----------
        function renderChips() {
            if (!chipsContainer || !statusSelect) return;
            const active = statusSelect.value;
            const chips = [{ status: "", label: "Todos", count: counts._total ?? 0 }];
            statusOrder.forEach(status => {
                const count = counts[status] || 0;
                if (count > 0 || status === active) chips.push({ status, label: status, count });
            });
            chipsContainer.innerHTML = chips.map(chip => `
                <button type="button" class="lv-chip${chip.status === active ? " is-active" : ""}"
                    data-status="${escapeAttribute(chip.status)}" aria-pressed="${chip.status === active}">
                    <span>${escapeHtml(chip.label)}</span><b>${chip.count}</b>
                </button>`).join("");
        }

        renderChips();

        // ---------- Painel lateral (drawer) ----------
        const backdrop = document.getElementById("leadDrawerBackdrop");
        const drawerContent = document.getElementById("leadDrawerContent");
        const closeButton = document.getElementById("leadDrawerClose");
        const skeletonTemplate = document.getElementById("leadDrawerSkeleton");
        const validating = new Set();
        let currentLeadId = null;
        let lastFocus = null;

        function showSkeleton(message) {
            drawerContent.innerHTML = "";
            drawerContent.appendChild(skeletonTemplate.content.cloneNode(true));
            const msg = drawerContent.querySelector("[data-skeleton-msg]");
            if (msg) msg.textContent = message;
        }

        function markActiveRow() {
            document.querySelectorAll(".lv-table tr.lead-row.is-sel").forEach(row => row.classList.remove("is-sel"));
            if (currentLeadId) findLeadRows(currentLeadId).forEach(row => row.classList.add("is-sel"));
        }

        async function fetchLead(leadId) {
            const response = await fetch(`/api/leads/${leadId}`, { headers: { "Accept": "application/json" } });
            const result = await response.json();
            if (!response.ok || !result.ok) throw new Error(result.message || "Lead não encontrado.");
            return result;
        }

        // Busca o lead e atualiza só a linha dele e, se estiver aberto, o painel.
        async function refreshLead(leadId) {
            const row = findLeadRow(leadId);
            const oldStatus = row ? row.dataset.status : null;
            const result = await fetchLead(leadId);
            replaceLeadRow(leadId, result.row_html);
            if (oldStatus !== null && oldStatus !== result.lead.status) {
                onStatusChanged(oldStatus, result.lead.status);
            }
            if (String(currentLeadId) === String(leadId) && !validating.has(String(leadId))) {
                drawerContent.innerHTML = result.drawer_html;
            }
            return result;
        }

        async function openDrawer(leadId, options = {}) {
            leadId = String(leadId);
            if (currentLeadId === null) lastFocus = document.activeElement;
            currentLeadId = leadId;
            drawer.classList.add("is-open");
            drawer.setAttribute("aria-hidden", "false");
            backdrop.hidden = false;
            document.body.classList.add("lv-drawer-open");
            markActiveRow();
            closeButton.focus({ preventScroll: true });

            if (validating.has(leadId)) {
                showSkeleton("Gerando o laudo… isso pode levar até 1 minuto.");
                return;
            }
            showSkeleton("Carregando lead…");
            try {
                await refreshLead(leadId);
                if (options.validate) runValidation(leadId, false);
            } catch (error) {
                if (currentLeadId === leadId) {
                    drawerContent.innerHTML = `<p class="lv-muted lv-drawer-error">${escapeHtml(error.message || "Não foi possível carregar o lead.")}</p>`;
                }
            }
        }

        function closeDrawer() {
            if (currentLeadId === null) return;
            currentLeadId = null;
            drawer.classList.remove("is-open");
            drawer.setAttribute("aria-hidden", "true");
            backdrop.hidden = true;
            document.body.classList.remove("lv-drawer-open");
            markActiveRow();
            if (lastFocus && document.contains(lastFocus)) lastFocus.focus({ preventScroll: true });
            lastFocus = null;
        }

        // Roda a análise de IA (endpoint existente) com skeleton no painel e na linha.
        async function runValidation(leadId, reanalisar) {
            leadId = String(leadId);
            if (validating.has(leadId)) return;
            validating.add(leadId);
            findLeadRows(leadId).forEach(row => row.classList.add("is-validating"));
            if (currentLeadId === leadId) {
                showSkeleton("Gerando o laudo… isso pode levar até 1 minuto.");
            }

            let message = null;
            let tone = "success";
            try {
                const response = await fetch(`/api/leads/${leadId}/pesquisar-ia-real`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ reanalisar: Boolean(reanalisar) })
                });
                const result = await response.json();
                if (response.ok && result.ok) {
                    message = "Laudo atualizado.";
                } else {
                    message = result.message || "Não foi possível gerar o laudo.";
                    tone = "error";
                }
            } catch (error) {
                message = "Não foi possível gerar o laudo agora. Verifique a conexão e tente de novo.";
                tone = "error";
            } finally {
                validating.delete(leadId);
            }

            try {
                await refreshLead(leadId);
            } catch (error) {
                findLeadRows(leadId).forEach(row => row.classList.remove("is-validating"));
            }
            showToast(message, tone);
        }

        function onStatusChanged(oldStatus, newStatus) {
            if (oldStatus === newStatus) return;
            if (oldStatus && counts[oldStatus] > 0) counts[oldStatus] -= 1;
            if (newStatus) counts[newStatus] = (counts[newStatus] || 0) + 1;
            renderChips();
        }

        document.addEventListener("click", (event) => {
            const validateRowButton = event.target.closest(".lv-table .js-validate-lead");
            if (validateRowButton) {
                openDrawer(validateRowButton.closest("tr.lead-row").dataset.leadId, { validate: true });
                return;
            }
            const openButton = event.target.closest(".lv-table .js-open-lead");
            if (openButton) {
                openDrawer(openButton.closest("tr.lead-row").dataset.leadId);
                return;
            }
            const drawerValidate = event.target.closest("#leadDrawer .js-drawer-validate");
            if (drawerValidate && currentLeadId) {
                const inner = drawerContent.querySelector(".lv-drawer-inner");
                runValidation(currentLeadId, inner?.dataset.validado === "1");
                return;
            }
            if (event.target.closest("#leadDrawerClose") || event.target === backdrop) {
                closeDrawer();
                return;
            }
            // Linha inteira clicável, exceto controles dentro dela.
            const row = event.target.closest(".lv-table tr.lead-row");
            if (row && !event.target.closest("a, button, select, input, label, form")) {
                openDrawer(row.dataset.leadId);
            }
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && currentLeadId !== null) {
                closeDrawer();
                return;
            }
            const row = event.target.closest?.(".lv-table tr.lead-row");
            if (row && event.target === row && (event.key === "Enter" || event.key === " ")) {
                event.preventDefault();
                openDrawer(row.dataset.leadId);
            }
        });

        const leadFromUrl = new URLSearchParams(location.search).get("lead");
        if (leadFromUrl && /^\d+$/.test(leadFromUrl)) openDrawer(leadFromUrl);

        return { onStatusChanged };
    }

    // -------------------------------------------------------------
    // 2. Capturar leads: busca, seleção e inclusão na lista de leads
    // -------------------------------------------------------------
    setupCapture();

    function setupCapture() {
        const form = document.getElementById("captureForm");
        if (!form) return;
        const submit = document.getElementById("captureSubmit");
        const status = document.getElementById("captureStatus");
        const results = document.getElementById("captureResults");
        const empty = document.getElementById("captureEmpty");
        const body = document.getElementById("captureBody");
        const checkAll = document.getElementById("captureAll");
        const addButton = document.getElementById("captureAdd");
        const countLabel = document.getElementById("captureCount");
        const selectedLabel = document.getElementById("captureSelected");
        let found = [];

        function setStatus(message, type) {
            status.textContent = message;
            status.className = `notice ${type || "info"}`;
        }

        function clearStatus() {
            status.className = "notice hidden";
            status.textContent = "";
        }

        function selectable() {
            return [...body.querySelectorAll('input[type="checkbox"]:not(:disabled)')];
        }

        function updateSelection() {
            const boxes = selectable();
            const checked = boxes.filter(box => box.checked).length;
            selectedLabel.textContent = checked === 0
                ? "Nenhuma empresa selecionada"
                : checked === 1 ? "1 empresa selecionada" : `${checked} empresas selecionadas`;
            addButton.disabled = checked === 0;
            checkAll.checked = boxes.length > 0 && checked === boxes.length;
            checkAll.indeterminate = checked > 0 && checked < boxes.length;
            checkAll.disabled = boxes.length === 0;
        }

        function rating(lead) {
            if (!lead.avaliacao) return "—";
            const total = lead.qtd_avaliacoes ?? 0;
            return `${escapeHtml(String(lead.avaliacao))} (${escapeHtml(String(total))})`;
        }

        function render(message) {
            body.innerHTML = found.map((lead, index) => `
                <tr data-index="${index}">
                    <td class="col-check">
                        <label class="check"><input type="checkbox" data-index="${index}"><span class="sr-only">Selecionar ${escapeHtml(lead.nome_empresa)}</span></label>
                    </td>
                    <td><span class="lead-name">${escapeHtml(lead.nome_empresa)}</span><span class="lead-sub">${escapeHtml(lead.endereco || "Endereço não informado")}</span></td>
                    <td>${escapeHtml(lead.telefone_whatsapp || "—")}</td>
                    <td>${/^https?:\/\//i.test(lead.site || "")
                        ? `<a href="${escapeAttribute(lead.site)}" target="_blank" rel="noopener noreferrer">Abrir site</a>`
                        : '<span class="badge bad">Sem site</span>'}</td>
                    <td class="num">${rating(lead)}</td>
                </tr>`).join("");
            countLabel.textContent = found.length === 1 ? "1 empresa encontrada" : `${found.length} empresas encontradas`;
            results.hidden = false;
            empty.hidden = true;
            if (message) setStatus(message, "info"); else clearStatus();
            updateSelection();
        }

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const data = Object.fromEntries(new FormData(form).entries());
            const cidade = String(data.cidade || "").trim();
            const estado = String(data.estado || "").trim().toUpperCase();
            // O estado entra na busca para evitar cidades com o mesmo nome.
            const payload = { nicho: String(data.nicho || "").trim(), cidade: estado ? `${cidade}, ${estado}` : cidade, limite: data.limite };

            submit.disabled = true;
            submit.textContent = "Buscando…";
            setStatus("Buscando empresas. Isso pode levar alguns segundos.", "info");
            results.hidden = true;

            try {
                const response = await fetch("/api/apify/buscar", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                const result = await response.json();
                if (!response.ok || !result.ok) {
                    found = [];
                    empty.hidden = false;
                    setStatus(response.status === 400 && !result.leads?.length && /token|\.env/i.test(result.message || "")
                        ? "A fonte de busca não está configurada. Veja em Configurações."
                        : (result.message || "Não foi possível concluir a busca."), "error");
                    return;
                }
                // A cidade e o estado ficam gravados separados no lead.
                found = (result.leads || []).map(lead => ({ ...lead, cidade, estado }));
                if (!found.length) {
                    empty.hidden = false;
                    setStatus(result.message || "Nenhuma empresa encontrada para essa busca.", "info");
                    return;
                }
                render("");
            } catch (error) {
                found = [];
                empty.hidden = false;
                setStatus("Erro ao buscar empresas. Verifique a conexão e tente novamente.", "error");
            } finally {
                submit.disabled = false;
                submit.textContent = "Buscar empresas";
            }
        });

        checkAll.addEventListener("change", () => {
            selectable().forEach(box => { box.checked = checkAll.checked; });
            updateSelection();
        });

        body.addEventListener("change", (event) => {
            if (event.target.matches('input[type="checkbox"]')) updateSelection();
        });

        addButton.addEventListener("click", async () => {
            const boxes = selectable().filter(box => box.checked);
            if (!boxes.length) return;
            const leads = boxes.map(box => found[Number(box.dataset.index)]).filter(Boolean);

            addButton.disabled = true;
            addButton.textContent = "Adicionando…";
            const result = await postJson("/api/apify/salvar-todos", { leads });
            addButton.textContent = "Adicionar selecionados aos leads";

            if (!result.ok) {
                setStatus(result.message || "Não foi possível adicionar os leads.", "error");
                updateSelection();
                return;
            }
            boxes.forEach(box => {
                box.checked = false;
                box.disabled = true;
                box.closest("tr").classList.add("is-saved");
            });
            const saved = result.saved ?? leads.length;
            const duplicated = result.duplicated ?? 0;
            let message = saved === 1 ? "1 lead adicionado." : `${saved} leads adicionados.`;
            if (duplicated) message += duplicated === 1 ? " 1 já estava na lista." : ` ${duplicated} já estavam na lista.`;
            setStatus(message, "success");
            updateSelection();
        });
    }

    // -------------------------------------------------------------
    // 3. Mensagens: editor de abordagem a partir dos fatos do laudo
    // -------------------------------------------------------------
    setupMessages();

    function setupMessages() {
        const app = document.getElementById("msgApp");
        if (!app) return;
        let items = [];
        try {
            items = JSON.parse(document.getElementById("msgData")?.textContent || "[]");
        } catch (error) {
            items = [];
        }
        if (!items.length) return;

        const nome = document.getElementById("msgNome");
        const meta = document.getElementById("msgMeta");
        const fatos = document.getElementById("msgFatos");
        const texto = document.getElementById("msgTexto");
        const copiar = document.getElementById("msgCopiar");
        const whats = document.getElementById("msgWhats");
        const enviada = document.getElementById("msgEnviada");
        const SENT = "Mensagem enviada";
        let current = null;

        // Cada frase só entra se o fato correspondente estiver no laudo.
        const FRASES = {
            sem_site: "vi que vocês ainda não têm um site próprio",
            site_terceirizado: "vi que o site de vocês fica em uma plataforma de terceiros",
            bio_agregador: "notei que o link da bio do Instagram leva para um agregador de links",
            bio_whatsapp: "notei que o link da bio do Instagram leva direto para o WhatsApp",
        };

        function observation(item) {
            const frases = item.fatos.map(fato => FRASES[fato.chave]).filter(Boolean);
            if (!frases.length) return "";
            return frases.length === 1 ? frases[0] : `${frases[0]} e ${frases[1]}`;
        }

        function buildMessage(item, tom) {
            const empresa = item.nome || "sua empresa";
            const obs = observation(item);
            const upper = (value) => value.charAt(0).toUpperCase() + value.slice(1);
            if (tom === "consultivo") {
                return [
                    `Olá! Tudo bem? Estive olhando a presença digital de ${empresa}.`,
                    obs ? `${upper(obs)}.` : "",
                    "Trabalho com criação de sites para negócios locais e posso mostrar, sem compromisso, como isso ficaria para vocês.",
                    "Faz sentido conversarmos?",
                ].filter(Boolean).join(" ");
            }
            if (tom === "descontraido") {
                return [
                    `Oi, pessoal de ${empresa}! Tudo certo?`,
                    obs ? `Dei uma olhada em vocês na internet e ${obs}.` : "Dei uma olhada em vocês na internet.",
                    "Eu faço sites para negócios locais e pensei em uma ideia para vocês. Posso mandar por aqui?",
                ].join(" ");
            }
            return [
                `Olá! Este é o contato de ${empresa}?`,
                obs ? `${upper(obs)}.` : "",
                "Eu crio sites para negócios locais. Posso enviar uma proposta rápida?",
            ].filter(Boolean).join(" ");
        }

        function currentTone() {
            return app.querySelector('input[name="tom"]:checked')?.value || "direto";
        }

        function updateWhatsLink() {
            if (current && current.whatsapp) {
                whats.href = `${current.whatsapp}?text=${encodeURIComponent(texto.value)}`;
                whats.classList.remove("is-disabled");
                whats.removeAttribute("aria-disabled");
                whats.title = "";
            } else {
                whats.removeAttribute("href");
                whats.classList.add("is-disabled");
                whats.setAttribute("aria-disabled", "true");
                whats.title = "Lead sem telefone cadastrado";
            }
        }

        function select(id) {
            current = items.find(item => String(item.id) === String(id)) || items[0];
            app.querySelectorAll(".msg-item").forEach(button => {
                const active = button.dataset.leadId === String(current.id);
                button.classList.toggle("is-sel", active);
                button.setAttribute("aria-current", active ? "true" : "false");
            });
            nome.textContent = current.nome;
            meta.textContent = [current.nicho, current.cidade].filter(Boolean).join(" · ");
            fatos.innerHTML = current.fatos.length
                ? current.fatos.map(fato => `<span class="badge ${escapeAttribute(fato.nivel)}">${escapeHtml(fato.rotulo)}</span>`).join("")
                : '<span class="muted">O laudo não registrou fatos para este lead.</span>';
            texto.value = buildMessage(current, currentTone());
            enviada.checked = current.status === SENT;
            updateWhatsLink();
        }

        app.addEventListener("click", (event) => {
            const button = event.target.closest(".msg-item");
            if (button) select(button.dataset.leadId);
        });

        app.querySelectorAll('input[name="tom"]').forEach(radio => {
            radio.addEventListener("change", () => {
                texto.value = buildMessage(current, currentTone());
                updateWhatsLink();
            });
        });

        texto.addEventListener("input", updateWhatsLink);

        copiar.addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(texto.value);
                showToast("Mensagem copiada.");
            } catch (error) {
                texto.select();
                showToast("Não foi possível copiar. Selecione o texto e copie manualmente.", "error");
            }
        });

        whats.addEventListener("click", (event) => {
            if (!whats.hasAttribute("href")) event.preventDefault();
        });

        enviada.addEventListener("change", async () => {
            const item = current;
            const newStatus = enviada.checked ? SENT : "Analisado";
            enviada.disabled = true;
            const result = await postJson(`/api/leads/${item.id}/status`, { status: newStatus });
            enviada.disabled = false;
            if (!result.ok) {
                if (current === item) enviada.checked = !enviada.checked;
                showToast(result.message || "Não foi possível atualizar o status.", "error");
                return;
            }
            item.status = newStatus;
            const badge = app.querySelector(`.msg-item[data-lead-id="${item.id}"] [data-msg-status]`);
            if (badge) {
                badge.textContent = newStatus === SENT ? "Enviada" : `Score ${item.score}`;
                badge.classList.toggle("good", newStatus === SENT);
            }
            showToast(newStatus === SENT ? "Lead marcado como mensagem enviada." : "Marcação removida.");
        });

        select(items[0].id);
    }

    // -------------------------------------------------------------
    // 4. Configurações: teste de conexão das fontes de captura
    // -------------------------------------------------------------
    document.addEventListener("click", async (event) => {
        const button = event.target.closest(".js-test-source");
        if (!button) return;
        const output = button.closest(".source")?.querySelector(".source-result");
        const label = button.textContent;
        button.disabled = true;
        button.textContent = "Testando…";

        let ok = false;
        let message = "Não foi possível testar a conexão.";
        try {
            const response = await fetch("/api/apify/test-connection", { method: "POST" });
            const result = await response.json();
            ok = response.ok && result.ok;
            // A resposta do servidor pode citar a conta; na tela fica só o resultado.
            message = ok
                ? "Conexão funcionando."
                : response.status === 401 ? "A chave configurada foi recusada pela fonte." : "A fonte não respondeu como esperado.";
        } catch (error) {
            message = "Erro de comunicação ao testar a conexão.";
        }
        if (output) {
            output.textContent = message;
            output.className = `notice source-result ${ok ? "success" : "error"}`;
        }
        button.disabled = false;
        button.textContent = label;
    });

    // -------------------------------------------------------------
    // 5. Menu do celular, avisos e exclusão
    // -------------------------------------------------------------
    const menuToggle = document.getElementById("menuToggle");
    const menuBackdrop = document.getElementById("menuBackdrop");

    function setMenu(open) {
        document.body.classList.toggle("menu-open", open);
        if (menuBackdrop) menuBackdrop.hidden = !open;
        if (menuToggle) {
            menuToggle.setAttribute("aria-expanded", String(open));
            menuToggle.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu");
        }
    }

    menuToggle?.addEventListener("click", () => setMenu(!document.body.classList.contains("menu-open")));
    menuBackdrop?.addEventListener("click", () => setMenu(false));
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && document.body.classList.contains("menu-open")) setMenu(false);
    });

    document.addEventListener("click", (event) => {
        const close = event.target.closest(".js-flash-close");
        if (close) close.closest(".flash")?.remove();
    });

    // Delegado: vale também para o formulário dentro da gaveta.
    document.addEventListener("submit", (event) => {
        if (!event.target.closest(".delete-form")) return;
        if (!confirm("Excluir este lead de forma permanente?")) event.preventDefault();
    });

    // -------------------------------------------------------------
    // Funções de apoio
    // -------------------------------------------------------------
    async function postJson(url, payload) {
        try {
            const response = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await response.json();
            return { ...data, ok: response.ok && data.ok };
        } catch (error) {
            return { ok: false, message: "Erro de comunicação com o servidor." };
        }
    }

    function showToast(message, type = "success") {
        const toast = document.getElementById("toastNotification");
        if (!toast) return;
        toast.textContent = message;
        toast.className = `toast ${type}`;
        toast.offsetWidth; // força o reflow para a transição
        toast.classList.add("show");
        clearTimeout(showToast.timer);
        showToast.timer = setTimeout(() => {
            toast.classList.remove("show");
            setTimeout(() => toast.classList.add("hidden"), 250);
        }, 2600);
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function escapeAttribute(value) {
        return escapeHtml(value).replaceAll("`", "&#096;");
    }
});
