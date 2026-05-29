document.addEventListener("DOMContentLoaded", () => {
    // -------------------------------------------------------------
    // 1. CRM Dynamic Status Updates
    // -------------------------------------------------------------
    const statusSelects = document.querySelectorAll(".crm-status-select");
    statusSelects.forEach(select => {
        select.addEventListener("change", async (event) => {
            const leadId = select.dataset.leadId;
            const newStatus = select.value;
            
            try {
                const response = await fetch(`/api/leads/${leadId}/status`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ status: newStatus })
                });
                const result = await response.json();
                
                if (response.ok && result.ok) {
                    showToast(`Status atualizado para: ${newStatus}`);
                } else {
                    showToast("Erro ao atualizar status.", "error");
                }
            } catch (error) {
                showToast("Erro de comunicação com o servidor.", "error");
            }
        });
    });

    // -------------------------------------------------------------
    // 2. AI Analysis Modal Trigger & Flow
    // -------------------------------------------------------------
    const aiModal = document.getElementById("aiModal");
    const closeAiModalBtn = document.getElementById("closeAiModal");
    const aiLoading = document.getElementById("aiLoading");
    const aiResults = document.getElementById("aiResults");
    
    // Modal fields
    const aiLeadName = document.getElementById("aiLeadName");
    const aiPotentialBadge = document.getElementById("aiPotentialBadge");
    const aiReasonText = document.getElementById("aiReasonText");
    const aiMessageText = document.getElementById("aiMessageText");
    const copyAiMessageBtn = document.getElementById("copyAiMessage");
    const sendAiWhatsappBtn = document.getElementById("sendAiWhatsapp");

    // Click handler for AI Buttons
    document.addEventListener("click", async (event) => {
        const aiButton = event.target.closest(".run-ai-btn");
        if (!aiButton) return;

        const card = aiButton.closest(".lead-card");
        if (!card) return;

        const leadId = card.dataset.leadId;
        const nome = card.dataset.nome;
        const nicho = card.dataset.nicho;
        const cidade = card.dataset.cidade;
        const siteQualidade = card.dataset.siteQualidade;
        const aiAnalisado = card.dataset.aiAnalisado;

        // Open modal
        aiModal.classList.remove("hidden");
        aiLeadName.textContent = nome;

        if (aiAnalisado === "1") {
            // Already analyzed: show results immediately
            showAiResults({
                potencial: card.dataset.aiPotencial,
                motivo: card.dataset.aiMotivo,
                sugestao: card.dataset.aiSugestao,
                whatsapp: card.querySelector(".whatsapp-btn")?.getAttribute("href") || ""
            });
        } else {
            // Not analyzed: show loading animation and call API
            showAiLoading();
            
            // Animate loading steps
            const steps = aiLoading.querySelectorAll(".step");
            steps.forEach(s => s.classList.remove("active"));
            
            let stepIndex = 0;
            steps[0].classList.add("active");
            
            const stepInterval = setInterval(() => {
                stepIndex++;
                if (stepIndex < steps.length) {
                    steps[stepIndex].classList.add("active");
                }
            }, 400);

            try {
                const startTime = Date.now();
                const response = await fetch(`/api/leads/${leadId}/analisar`, {
                    method: "POST"
                });
                const result = await response.json();
                
                // Enforce minimum animation time (1.5s) for a premium feel
                const duration = Date.now() - startTime;
                const delay = Math.max(0, 1500 - duration);
                
                setTimeout(() => {
                    clearInterval(stepInterval);
                    if (response.ok && result.ok) {
                        // Update card dataset
                        card.dataset.aiAnalisado = "1";
                        card.dataset.aiPotencial = result.ai_potencial;
                        card.dataset.aiMotivo = result.ai_motivo;
                        card.dataset.ai_sugestao = result.ai_sugestao;
                        card.dataset.aiSugestao = result.ai_sugestao;

                        // Update card UI
                        updateCardUiAfterAnalysis(card, result);

                        // Show results
                        showAiResults({
                            potencial: result.ai_potencial,
                            motivo: result.ai_motivo,
                            sugestao: result.ai_sugestao,
                            whatsapp: card.querySelector(".whatsapp-btn")?.getAttribute("href") || ""
                        });
                    } else {
                        showToast("Erro ao processar análise da IA.", "error");
                        aiModal.classList.add("hidden");
                    }
                }, delay);

            } catch (error) {
                clearInterval(stepInterval);
                showToast("Falha de conexão com a IA.", "error");
                aiModal.classList.add("hidden");
            }
        }
    });

    // Close Modal Event
    if (closeAiModalBtn) {
        closeAiModalBtn.addEventListener("click", () => {
            aiModal.classList.add("hidden");
        });
    }

    window.addEventListener("click", (event) => {
        if (event.target === aiModal) {
            aiModal.classList.add("hidden");
        }
    });

    // Copy AI Message
    if (copyAiMessageBtn) {
        copyAiMessageBtn.addEventListener("click", async () => {
            const originalText = copyAiMessageBtn.textContent;
            try {
                await navigator.clipboard.writeText(aiMessageText.value || "");
                copyAiMessageBtn.textContent = "📋 Copiado!";
                setTimeout(() => {
                    copyAiMessageBtn.textContent = originalText;
                }, 1600);
            } catch (error) {
                copyAiMessageBtn.textContent = "Erro ao copiar";
                setTimeout(() => {
                    copyAiMessageBtn.textContent = originalText;
                }, 1600);
            }
        });
    }

    function showAiLoading() {
        aiLoading.classList.remove("hidden");
        aiResults.classList.add("hidden");
    }

    function showAiResults(data) {
        aiLoading.classList.add("hidden");
        aiResults.classList.remove("hidden");

        // Format Potential Badge
        aiPotentialBadge.textContent = `Potencial ${data.potencial}`;
        aiPotentialBadge.className = `potential-badge ${priorityClass(data.potencial)}`;

        // Set reason and suggestion
        aiReasonText.textContent = data.motivo;
        aiMessageText.value = data.sugestao;

        // Configure Whatsapp Link
        if (sendAiWhatsappBtn) {
            // Update Whatsapp link destination with new text
            let phoneLink = data.whatsapp.split("?")[0] || "";
            if (phoneLink) {
                sendAiWhatsappBtn.setAttribute("href", `${phoneLink}?text=${encodeURIComponent(data.sugestao)}`);
                sendAiWhatsappBtn.style.display = "inline-flex";
            } else {
                sendAiWhatsappBtn.style.display = "none";
            }
        }
    }

    function updateCardUiAfterAnalysis(card, result) {
        // Keep quick verification action text aligned with lead-quality flow
        const aiBtn = card.querySelector(".run-ai-btn");
        if (aiBtn) {
            aiBtn.textContent = "🪄 Verificar qualidade do lead";
        }

        // Set AI Analyzed Badge in header if not already present
        const badgesContainer = card.querySelector(".card-badges");
        if (badgesContainer && !card.querySelector(".ai-badge-card")) {
            const aiBadge = document.createElement("span");
            aiBadge.className = "ai-badge-card";
            aiBadge.textContent = "🤖 IA Analisou";
            badgesContainer.insertBefore(aiBadge, badgesContainer.firstChild);
        }

        // Change Potential Badge Class
        const potentialTag = card.querySelector(".potential-tag");
        if (potentialTag) {
            potentialTag.textContent = `Potencial ${result.ai_potencial}`;
            potentialTag.className = `potential-tag ${priorityClass(result.ai_potencial)}`;
        }

        // Update status select dropdown
        const statusSelect = card.querySelector(".crm-status-select");
        if (statusSelect) {
            statusSelect.value = "Analisado";
        }

        // Replace old static diagnosis text with dynamic AI preview
        const diagnosisParagraph = card.querySelector(".diagnosis");
        let aiPreview = card.querySelector(".ai-preview-box");
        
        if (diagnosisParagraph) {
            diagnosisParagraph.remove();
        }
        
        if (!aiPreview) {
            aiPreview = document.createElement("div");
            aiPreview.className = "ai-preview-box";
            card.insertBefore(aiPreview, card.querySelector(".card-actions"));
        }
        
        const truncatedMotivo = result.ai_motivo.length > 140 ? result.ai_motivo.slice(0, 137) + "..." : result.ai_motivo;
        aiPreview.innerHTML = `
            <span class="ai-box-title">🤖 Pré-análise do lead:</span>
            <p class="ai-box-motivo">${truncatedMotivo}</p>
        `;

        // Update WhatsApp action button href with the new message
        const whatsappBtn = card.querySelector(".whatsapp-btn");
        if (whatsappBtn) {
            const originalHref = whatsappBtn.getAttribute("href");
            const phone = originalHref.split("?")[0] || "";
            whatsappBtn.setAttribute("href", `${phone}?text=${encodeURIComponent(result.ai_sugestao)}`);
        }
    }

    // -------------------------------------------------------------
    // 3. Apify Search Results Flow
    // -------------------------------------------------------------
    const googlePlacesForm = document.getElementById("googlePlacesForm");
    const placesResults = document.getElementById("placesResults");
    const placesStatus = document.getElementById("placesStatus");
    const captureBeforeSearch = document.getElementById("captureBeforeSearch");
    const resultsToolbar = document.getElementById("resultsToolbar");
    const resultsCount = document.getElementById("resultsCount");
    const resultsMessage = document.getElementById("resultsMessage");
    const saveAllButton = document.getElementById("saveAllLeads");
    let foundLeads = [];

    if (googlePlacesForm) {
        googlePlacesForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            const formData = new FormData(googlePlacesForm);
            const payload = Object.fromEntries(formData.entries());

            setPlacesStatus("🔍 Buscando empresas reais na Apify...", "info");
            placesStatus.classList.add("loading-dots");
            placesResults.innerHTML = "";
            resultsToolbar.classList.add("hidden");
            if (captureBeforeSearch) captureBeforeSearch.classList.add("hidden");

            try {
                const response = await fetch("/api/apify/buscar", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                const data = await response.json();

                if (!response.ok || !data.ok) {
                foundLeads = [];
                setPlacesStatus(data.message || "Não foi possível concluir a busca.", "error");
                placesStatus.classList.remove("loading-dots");
                return;
            }

            foundLeads = data.leads || [];
            placesStatus.classList.remove("loading-dots");
            renderPlacesResults(foundLeads, data.message);
        } catch (error) {
            foundLeads = [];
            setPlacesStatus("Erro inesperado ao buscar leads. Verifique a conexão e tente novamente.", "error");
            placesStatus.classList.remove("loading-dots");
        }
    });
    }

    if (saveAllButton) {
        saveAllButton.addEventListener("click", async () => {
            if (!foundLeads.length) return;
            
            saveAllButton.disabled = true;
            saveAllButton.textContent = "Salvando...";
            const result = await postJson("/api/apify/salvar-todos", { leads: foundLeads });
            
            setPlacesStatus(result.message || "Leads processados.", result.ok ? "success" : "error");
            saveAllButton.textContent = "💾 Salvar todos para validar";
            saveAllButton.disabled = false;
        });
    }

    function renderPlacesResults(leads, message) {
        placesResults.innerHTML = "";

        if (!leads.length) {
            setPlacesStatus(message || "Nenhum lead encontrado para essa busca.", "info");
            if (captureBeforeSearch) captureBeforeSearch.classList.remove("hidden");
            return;
        }

        hidePlacesStatus();
        resultsToolbar.classList.remove("hidden");
        resultsCount.textContent = `${leads.length} lead(s) encontrado(s)`;
        resultsMessage.textContent = message || "";

        leads.forEach((lead, index) => {
            const card = document.createElement("article");
            card.className = `lead-card capture-lead-card potential-${priorityClass(lead.prioridade)}`;
            card.innerHTML = `
                <header>
                    <div>
                        <span class="tag-nicho">${escapeHtml(lead.nicho)}</span>
                        <h2>${escapeHtml(lead.nome_empresa)}</h2>
                        <p class="location"><span class="loc-icon">📍</span> ${escapeHtml(lead.cidade)}</p>
                    </div>
                    <span class="potential-tag ${priorityClass(lead.prioridade)}">${escapeHtml(lead.prioridade === 'Alta' ? 'Potencial Alto' : lead.prioridade === 'Média' ? 'Potencial Médio' : 'Potencial Baixo')}</span>
                </header>
                <div class="lead-grid">
                    <span>Endereço</span>
                    <strong>${escapeHtml(lead.endereco || "Não informado")}</strong>
                    <span>Telefone</span>
                    <strong>${escapeHtml(lead.telefone_whatsapp || "Não informado")}</strong>
                    <span>Site</span>
                    <strong>${lead.site ? `<a href="${escapeAttribute(lead.site)}" target="_blank" rel="noreferrer" class="site-link">${escapeHtml(lead.site)}</a>` : '<span class="no-site-badge">Não tem site</span>'}</strong>
                    <span>Avaliação</span>
                    <strong>${formatRating(lead)}</strong>
                </div>
                <p class="diagnosis">${escapeHtml(lead.diagnostico)}</p>
                <footer class="card-actions">
                    <button class="primary-button save-found-lead" type="button" data-index="${index}">Salvar lead</button>
                    <button class="secondary-button validate-found-lead" type="button" data-index="${index}">Validar lead</button>
                    <button class="ghost-button discard-found-lead" type="button" data-index="${index}">Descartar</button>
                    ${lead.google_maps_url ? `<a class="icon-button maps-btn" href="${escapeAttribute(lead.google_maps_url)}" target="_blank" rel="noreferrer">🗺️ Maps</a>` : ""}
                </footer>
            `;
            placesResults.appendChild(card);
        });
    }

    document.addEventListener("click", async (event) => {
        const saveButton = event.target.closest(".save-found-lead");
        if (!saveButton) return;

        const lead = foundLeads[Number(saveButton.dataset.index)];
        if (!lead) return;

        saveButton.disabled = true;
        saveButton.textContent = "Salvando...";
        
        const result = await postJson("/api/apify/salvar", { lead });
        
        if (result.ok) {
            saveButton.textContent = "✓ Salvo";
            saveButton.className = "icon-button success-btn";
            showToast("Lead salvo no CRM com sucesso!");
        } else {
            saveButton.textContent = result.reason === "duplicado" ? "Duplicado" : "Erro";
            saveButton.className = "icon-button warning-btn";
            showToast(result.message || "Lead já cadastrado.", "info");
        }
    });

    // -------------------------------------------------------------
    // Helper Functions
    // -------------------------------------------------------------
    async function postJson(url, payload) {
        try {
            const response = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await response.json();
            return { ok: response.ok && data.ok, ...data };
        } catch (error) {
            return { ok: false, message: "Erro de comunicação com o servidor." };
        }
    }

    function showToast(message, type = "success") {
        const toast = document.getElementById("toastNotification");
        if (!toast) return;

        toast.textContent = message;
        toast.className = `toast ${type}`;
        toast.classList.remove("hidden");
        
        // Triggers reflow for transition
        toast.offsetWidth; 
        toast.classList.add("show");

        setTimeout(() => {
            toast.classList.remove("show");
            setTimeout(() => {
                toast.classList.add("hidden");
            }, 300);
        }, 2200);
    }

    function setPlacesStatus(message, type) {
        if (!placesStatus) return;
        placesStatus.textContent = message;
        placesStatus.className = `status-panel ${type || "info"}`;
        placesStatus.classList.remove("hidden");
    }

    function hidePlacesStatus() {
        if (!placesStatus) return;
        placesStatus.className = "status-panel hidden";
        placesStatus.textContent = "";
    }

    function priorityClass(priority) {
        const str = String(priority || "").toLowerCase();
        if (str.includes("alta") || str.includes("alto")) return "alta";
        if (str.includes("media") || str.includes("medio")) return "media";
        return "baixa";
    }

    function formatRating(lead) {
        if (!lead.avaliacao) return "Não informado";
        const count = lead.qtd_avaliacoes ?? 0;
        return `⭐ ${escapeHtml(String(lead.avaliacao))} (${escapeHtml(String(count))} avaliações)`;
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
    
    // Copy simple messages on cards
    document.addEventListener("click", async (event) => {
        const copyButton = event.target.closest(".copy-message");
        if (!copyButton) return;

        const originalText = copyButton.textContent;
        try {
            await navigator.clipboard.writeText(copyButton.dataset.message || "");
            copyButton.textContent = "Copiado";
            setTimeout(() => {
                copyButton.textContent = originalText;
            }, 1600);
        } catch (error) {
            copyButton.textContent = "Erro ao copiar";
            setTimeout(() => {
                copyButton.textContent = originalText;
            }, 1600);
        }
    });

    // Handle delete lead alerts
    const deleteForms = document.querySelectorAll(".delete-form");
    deleteForms.forEach(form => {
        form.addEventListener("submit", (e) => {
            if (!confirm("Excluir este lead de forma permanente?")) {
                e.preventDefault();
            }
        });
    });

    // -------------------------------------------------------------
    // 4. Real AI & Web Search Modal Trigger & Flow
    // -------------------------------------------------------------
    const realAiModal = document.getElementById("realAiModal");
    const closeRealAiModal = document.getElementById("closeRealAiModal");
    const closeRealAiModalFooter = document.getElementById("closeRealAiModalFooter");
    const realAiLoading = document.getElementById("realAiLoading");
    const realAiResults = document.getElementById("realAiResults");
    const realAiConnectionIssue = document.getElementById("realAiConnectionIssue");
    const runLocalFallbackBtn = document.getElementById("runLocalFallbackBtn");
    
    const realAiLeadName = document.getElementById("realAiLeadName");
    const realAiLeadMeta = document.getElementById("realAiLeadMeta");
    const realAiDate = document.getElementById("realAiDate");
    const realAiScore = document.getElementById("realAiScore");
    const realAiBadges = document.getElementById("realAiBadges");
    const realAiExiste = document.getElementById("realAiExiste");
    const realAiAtividade = document.getElementById("realAiAtividade");
    const realAiStatusProvavel = document.getElementById("realAiStatusProvavel");
    const realAiConfianca = document.getElementById("realAiConfianca");
    const realAiWhatsLead = document.getElementById("realAiWhatsLead");
    const realAiWhatsInsta = document.getElementById("realAiWhatsInsta");
    const realAiWhatsSite = document.getElementById("realAiWhatsSite");
    const realAiWhatsWaMe = document.getElementById("realAiWhatsWaMe");
    const realAiWhatsCompat = document.getElementById("realAiWhatsCompat");
    const realAiWhatsConfianca = document.getElementById("realAiWhatsConfianca");
    const realAiWhatsObs = document.getElementById("realAiWhatsObs");
    const realAiInstagramEncontrado = document.getElementById("realAiInstagramEncontrado");
    const realAiInstagramLink = document.getElementById("realAiInstagramLink");
    const realAiInstagramTipoLink = document.getElementById("realAiInstagramTipoLink");
    const realAiInstagramObs = document.getElementById("realAiInstagramObs");
    const realAiSiteEncontrado = document.getElementById("realAiSiteEncontrado");
    const realAiTipoSite = document.getElementById("realAiTipoSite");
    const realAiQualidadeSite = document.getElementById("realAiQualidadeSite");
    const realAiMotivoSite = document.getElementById("realAiMotivoSite");
    const realAiResumoCurto = document.getElementById("realAiResumoCurto");
    const realAiReasonText = document.getElementById("realAiReasonText");
    const realAiProblema = document.getElementById("realAiProblema");
    const realAiOferta = document.getElementById("realAiOferta");
    const realAiPreco = document.getElementById("realAiPreco");
    const realAiAprovado = document.getElementById("realAiAprovado");
    const realAiPrioridade = document.getElementById("realAiPrioridade");
    const realAiMotivoPrioridade = document.getElementById("realAiMotivoPrioridade");
    const realAiProximoPasso = document.getElementById("realAiProximoPasso");
    const realAiPotentialBadge = document.getElementById("realAiPotentialBadge");
    const realAiDecisionBadge = document.getElementById("realAiDecisionBadge");
    const realAiPriorityBadge = document.getElementById("realAiPriorityBadge");
    const realAiResumoAcao = document.getElementById("realAiResumoAcao");
    const realAiMessageText = document.getElementById("realAiMessageText");
    
    const copyRealAiSummaryBtn = document.getElementById("copyRealAiSummary");
    const copyRealAiMessageBtn = document.getElementById("copyRealAiMessage");
    const regenerateApproachBtn = document.getElementById("regenerateApproachBtn");
    const realAiSourcesSection = document.getElementById("realAiSourcesSection");
    const realAiSourcesList = document.getElementById("realAiSourcesList");
    const reanalyzeRealAiBtn = document.getElementById("reanalyzeRealAiBtn");

    let currentRealAiLeadCard = null;

    document.addEventListener("click", async (event) => {
        const revalidateButton = event.target.closest(".revalidate-lead-btn");
        if (revalidateButton) {
            const card = revalidateButton.closest(".lead-card");
            if (!card) return;
            currentRealAiLeadCard = card;
            realAiModal.classList.remove("hidden");
            realAiLeadName.textContent = card.dataset.nome || "Lead";
            triggerRealAiFetch(card.dataset.leadId, card, true);
            return;
        }

        const realAiBtn = event.target.closest(".run-real-ai-btn");
        if (!realAiBtn) return;

        const card = realAiBtn.closest(".lead-card");
        if (!card) return;

        currentRealAiLeadCard = card;
        const leadId = card.dataset.leadId;
        const nome = card.dataset.nome;
        
        realAiModal.classList.remove("hidden");
        realAiLeadName.textContent = nome;

        // Check if there is already an analysis result in card dataset
        const hasResult = card.dataset.iaRealResultado && card.dataset.iaRealResultado.trim() !== "";
        if (hasResult) {
            try {
                const parsedResult = JSON.parse(card.dataset.iaRealResultado);
                showRealAiResults({
                    data: parsedResult,
                    score: card.dataset.iaRealScore,
                    potencial: card.dataset.iaRealPotencial,
                    fontes: JSON.parse(card.dataset.iaRealFontes || "[]"),
                    analisado_em: card.dataset.analisadoEm
                }, card);
            } catch (err) {
                // If parsing fails, fall back to triggering fetch
                triggerRealAiFetch(leadId, card, false);
            }
        } else {
            triggerRealAiFetch(leadId, card, false);
        }
    });

    document.addEventListener("click", (event) => {
        const discardButton = event.target.closest(".discard-found-lead");
        if (!discardButton) return;
        discardButton.closest(".capture-lead-card")?.remove();
        showToast("Lead descartado da revisão.", "info");
    });

    document.addEventListener("click", async (event) => {
        const validateButton = event.target.closest(".validate-found-lead");
        if (!validateButton) return;
        if (validateButton.dataset.ready === "1") {
            window.location.href = "/dashboard#leads-section";
            return;
        }

        const lead = foundLeads[Number(validateButton.dataset.index)];
        if (!lead) return;

        validateButton.disabled = true;
        validateButton.textContent = "Salvando...";
        const result = await postJson("/api/apify/salvar", { lead });
        if (!(result.ok || result.reason === "duplicado")) {
            validateButton.textContent = "Erro";
            showToast(result.message || "Não foi possível salvar para validar.", "error");
            return;
        }
        validateButton.disabled = false;
        validateButton.textContent = "Abrir em Leads";
        validateButton.dataset.ready = "1";
        showToast("Lead preparado para validação no painel de Leads.");
    });

    async function triggerRealAiFetch(leadId, card, reanalisar) {
        showRealAiLoading();

        // Animate steps
        const steps = realAiLoading.querySelectorAll(".step");
        steps.forEach(s => s.classList.remove("active"));
        
        let stepIndex = 0;
        steps[0].classList.add("active");
        
        const stepInterval = setInterval(() => {
            stepIndex++;
            if (stepIndex < steps.length) {
                steps[stepIndex].classList.add("active");
            }
        }, 500);

        try {
            const startTime = Date.now();
            const response = await fetch(`/api/leads/${leadId}/pesquisar-ia-real`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ reanalisar: reanalisar })
            });
            const result = await response.json();

            const duration = Date.now() - startTime;
            const delay = Math.max(0, 1500 - duration);

            setTimeout(() => {
                clearInterval(stepInterval);
                if (response.ok && result.ok) {
                    // Update card dataset
                    card.dataset.iaRealResultado = JSON.stringify(result.data);
                    card.dataset.iaRealScore = result.score;
                    card.dataset.iaRealPotencial = result.potencial;
                    card.dataset.iaRealFontes = JSON.stringify(result.fontes || []);
                    card.dataset.analisadoEm = result.analisado_em || new Date().toLocaleString();

                    // Update CRM UI
                    updateCardUiAfterRealAnalysis(card, result);

                    // Show results in modal
                    showRealAiResults(result, card);
                } else {
                    const errMsg = result.message || "Erro desconhecido ao executar pesquisa com IA.";
                    if (result.connection_issue) {
                        showRealAiConnectionIssue(errMsg || "IA indisponível neste ambiente");
                    } else {
                        showToast(errMsg, "error");
                        realAiModal.classList.add("hidden");
                    }
                }
            }, delay);
        } catch (error) {
            clearInterval(stepInterval);
            showRealAiConnectionIssue("IA indisponível neste ambiente");
        }
    }

    function showRealAiLoading() {
        realAiLoading.classList.remove("hidden");
        realAiResults.classList.add("hidden");
        if (realAiConnectionIssue) {
            realAiConnectionIssue.classList.add("hidden");
        }
        reanalyzeRealAiBtn.style.display = "none";
    }

    function showRealAiResults(result, card) {
        realAiLoading.classList.add("hidden");
        realAiResults.classList.remove("hidden");
        if (realAiConnectionIssue) {
            realAiConnectionIssue.classList.add("hidden");
        }
        reanalyzeRealAiBtn.style.display = "inline-flex";

        const data = result.data;

        // Header and Date
        realAiDate.textContent = `Analisado em: ${result.analisado_em || 'Recente'}`;
        realAiScore.textContent = `${result.score || 0}/100`;
        if (realAiLeadMeta) {
            realAiLeadMeta.textContent = `${card.dataset.cidade || "Cidade não informada"} • ${card.dataset.nicho || "Nicho não informado"}`;
        }

        realAiExiste.textContent = capitalizeFirstLetter(data.empresa_existe || "incerto");
        realAiAtividade.textContent = capitalizeFirstLetter(data.sinais_atividade || "incerto");
        realAiStatusProvavel.textContent = capitalizeFirstLetter((data.status_provavel || "incerta").replaceAll("_", " "));
        realAiConfianca.textContent = `${Number(data.confianca_verificacao || 0)}/100`;

        realAiWhatsLead.textContent = data.whatsapp_numero_informado || card.dataset.telefone || "não informado";
        realAiWhatsInsta.textContent = data.whatsapp_numero_instagram || "não identificado";
        realAiWhatsSite.textContent = data.whatsapp_numero_site || "não identificado";
        realAiWhatsWaMe.textContent = data.whatsapp_numero_wa_me || "não identificado";
        realAiWhatsCompat.textContent = capitalizeFirstLetter((data.compatibilidade_whatsapp || "incerto").replaceAll("_", " "));
        realAiWhatsConfianca.textContent = capitalizeFirstLetter(data.confianca_whatsapp || "baixa");
        realAiWhatsObs.textContent = data.observacao_whatsapp || "Sem observação específica para WhatsApp.";

        realAiInstagramEncontrado.textContent = capitalizeFirstLetter(data.instagram_encontrado || "incerto");
        realAiInstagramLink.textContent = capitalizeFirstLetter(data.instagram_bio_tem_link || "incerto");
        realAiInstagramTipoLink.textContent = formatInstagramLinkType(data.instagram_tipo_link_bio || "nao_identificado");
        realAiInstagramObs.textContent = data.instagram_observacao_oportunidade || "Sem observação específica para Instagram.";

        realAiSiteEncontrado.textContent = capitalizeFirstLetter(data.site_encontrado || "incerto");
        realAiTipoSite.textContent = formatSiteType(data.tipo_site || "incerto");
        realAiQualidadeSite.textContent = capitalizeFirstLetter(data.qualidade_site || "incerta");
        realAiMotivoSite.textContent = data.motivo_qualidade_site || "Sem evidências suficientes para classificar o site com confiança.";
        realAiResumoCurto.textContent = data.diagnostico || "Sem resumo geral disponível.";

        // Sections
        realAiReasonText.textContent = data.diagnostico || "Sem diagnóstico disponível.";
        realAiProblema.textContent = data.problema_detectado || "Nenhum detectado.";
        realAiOferta.textContent = data.oferta_recomendada || "Nenhuma sugestão.";
        realAiPreco.textContent = data.preco_sugerido || "Sob consulta";
        realAiAprovado.textContent = capitalizeFirstLetter((data.lead_aprovado_abordagem || "com_ressalvas").replaceAll("_", " "));
        realAiPrioridade.textContent = capitalizeFirstLetter(data.prioridade || "media");
        realAiMotivoPrioridade.textContent = data.motivo_prioridade || "Prioridade definida por sinais públicos de presença digital e consistência de contato.";
        realAiProximoPasso.textContent = data.proximo_passo || "Validar abordagem com mensagem curta e confirmar o canal mais confiável.";

        // Potential Badge
        const potencial = result.potencial || "baixo";
        realAiPotentialBadge.textContent = `Potencial ${capitalizeFirstLetter(potencial)}`;
        realAiPotentialBadge.className = `potential-badge ${priorityClass(potencial)}`;
        if (realAiDecisionBadge) {
            const aprov = String(data.lead_aprovado_abordagem || "com_ressalvas").toLowerCase();
            if (aprov === "sim") {
                realAiDecisionBadge.className = "badge good";
                realAiDecisionBadge.textContent = "Aprovado";
                if (realAiResumoAcao) realAiResumoAcao.textContent = "Abordar agora";
            } else if (aprov === "nao") {
                realAiDecisionBadge.className = "badge bad";
                realAiDecisionBadge.textContent = "Descartar";
                if (realAiResumoAcao) realAiResumoAcao.textContent = "Descartar lead";
            } else {
                realAiDecisionBadge.className = "badge warn";
                realAiDecisionBadge.textContent = "Validar melhor";
                if (realAiResumoAcao) realAiResumoAcao.textContent = "Investigar melhor";
            }
        }
        if (realAiPriorityBadge) {
            const p = String(data.prioridade || "media").toLowerCase();
            realAiPriorityBadge.className = `badge ${p.includes("alta") ? "good" : p.includes("baixa") ? "bad" : "warn"}`;
            realAiPriorityBadge.textContent = `Prioridade ${capitalizeFirstLetter(p)}`;
        }
        renderLaudoBadges(data);

        // Message
        realAiMessageText.value = data.mensagem_whatsapp || "";

        // Sources List
        realAiSourcesList.innerHTML = "";
        const fontes = result.fontes || [];
        if (fontes && fontes.length > 0) {
            realAiSourcesSection.classList.remove("hidden");
            fontes.forEach(url => {
                const li = document.createElement("li");
                try {
                    const parsedUrl = new URL(url);
                    const domain = parsedUrl.hostname.replace("www.", "");
                    li.innerHTML = `<a href="${url}" target="_blank" rel="noreferrer" style="color: #a5f3fc; text-decoration: underline;">${domain}</a> — Link da pesquisa`;
                } catch (e) {
                    li.textContent = url;
                }
                realAiSourcesList.appendChild(li);
            });
        } else {
            realAiSourcesSection.classList.add("hidden");
        }
    }

    function showRealAiConnectionIssue(message) {
        realAiLoading.classList.add("hidden");
        realAiResults.classList.add("hidden");
        if (realAiConnectionIssue) {
            realAiConnectionIssue.classList.remove("hidden");
            const issueText = realAiConnectionIssue.querySelector("p");
            if (issueText) {
                issueText.textContent = message || "Não foi possível conectar à OpenAI neste ambiente. Verifique firewall, antivírus, proxy ou rode o app em ambiente com acesso externo.";
            }
        }
        reanalyzeRealAiBtn.style.display = "none";
    }

    function updateCardUiAfterRealAnalysis(card, result) {
        // Update main action button text
        const realBtn = card.querySelector(".run-real-ai-btn");
        if (realBtn) {
            realBtn.textContent = "📋 Ver laudo do lead";
        }

        // Set Real AI Analyzed Badge in header
        const badgesContainer = card.querySelector(".card-badges");
        if (badgesContainer) {
            // Remove simulated badge if present
            const oldBadge = badgesContainer.querySelector(".ai-badge-card");
            if (oldBadge) {
                oldBadge.remove();
            }
            
            // Add new Real AI Badge
            const realBadge = document.createElement("span");
            realBadge.className = "ai-badge-card";
            realBadge.style.background = "rgba(168, 85, 247, 0.12)";
            realBadge.style.borderColor = "rgba(168, 85, 247, 0.3)";
            realBadge.style.color = "#c084fc";
            realBadge.textContent = "🌐 IA Real Analisou";
            badgesContainer.insertBefore(realBadge, badgesContainer.firstChild);
        }

        // Update status dropdown selection
        const statusSelect = card.querySelector(".crm-status-select");
        if (statusSelect) {
            statusSelect.value = "Analisado";
        }

        // Update preview description box
        const diagText = result.data.diagnostico || "Laudo concluído com foco em verificação de qualidade do lead.";
        const truncatedMotivo = diagText.length > 140 ? diagText.slice(0, 137) + "..." : diagText;
        const diagnosisParagraph = card.querySelector(".diagnosis");
        let aiPreview = card.querySelector(".ai-preview-box");
        
        if (diagnosisParagraph) {
            diagnosisParagraph.remove();
        }
        
        if (!aiPreview) {
            aiPreview = document.createElement("div");
            aiPreview.className = "ai-preview-box";
            card.insertBefore(aiPreview, card.querySelector(".card-actions"));
        }
        
        aiPreview.innerHTML = `
            <span class="ai-box-title" style="color: #c084fc;">📋 Laudo de Verificação:</span>
            <p class="ai-box-motivo" style="color: #f3e8ff;">${truncatedMotivo}</p>
        `;
    }

    // Modal control actions
    if (closeRealAiModal) {
        closeRealAiModal.addEventListener("click", () => realAiModal.classList.add("hidden"));
    }
    if (closeRealAiModalFooter) {
        closeRealAiModalFooter.addEventListener("click", () => realAiModal.classList.add("hidden"));
    }
    window.addEventListener("click", (event) => {
        if (event.target === realAiModal) {
            realAiModal.classList.add("hidden");
        }
    });

    // Reanalyze button trigger
    if (reanalyzeRealAiBtn) {
        reanalyzeRealAiBtn.addEventListener("click", () => {
            if (currentRealAiLeadCard) {
                const leadId = currentRealAiLeadCard.dataset.leadId;
                triggerRealAiFetch(leadId, currentRealAiLeadCard, true);
            }
        });
    }

    // Message copying logic for real AI message
    if (copyRealAiMessageBtn) {
        copyRealAiMessageBtn.addEventListener("click", async () => {
            const originalText = copyRealAiMessageBtn.textContent;
            try {
                await navigator.clipboard.writeText(realAiMessageText.value || "");
                copyRealAiMessageBtn.textContent = "📋 Copiado!";
                setTimeout(() => copyRealAiMessageBtn.textContent = originalText, 1600);
            } catch (error) {
                copyRealAiMessageBtn.textContent = "Erro ao copiar";
                setTimeout(() => copyRealAiMessageBtn.textContent = originalText, 1600);
            }
        });
    }

    if (regenerateApproachBtn) {
        regenerateApproachBtn.addEventListener("click", () => {
            if (currentRealAiLeadCard) {
                const leadId = currentRealAiLeadCard.dataset.leadId;
                triggerRealAiFetch(leadId, currentRealAiLeadCard, true);
            }
        });
    }

    if (runLocalFallbackBtn) {
        runLocalFallbackBtn.addEventListener("click", async () => {
            if (!currentRealAiLeadCard) {
                showToast("Lead não encontrado para fallback local.", "error");
                return;
            }
            const leadId = currentRealAiLeadCard.dataset.leadId;
            try {
                const response = await fetch(`/api/leads/${leadId}/analisar`, { method: "POST" });
                const result = await response.json();
                if (!(response.ok && result.ok)) {
                    throw new Error(result.message || "Falha no fallback local.");
                }

                currentRealAiLeadCard.dataset.aiAnalisado = "1";
                currentRealAiLeadCard.dataset.aiPotencial = result.ai_potencial;
                currentRealAiLeadCard.dataset.aiMotivo = result.ai_motivo;
                currentRealAiLeadCard.dataset.aiSugestao = result.ai_sugestao;
                updateCardUiAfterAnalysis(currentRealAiLeadCard, result);
                showToast("Fallback local executado com sucesso.");
                realAiModal.classList.add("hidden");
            } catch (err) {
                showToast("Não foi possível executar o fallback local.", "error");
            }
        });
    }

    if (copyRealAiSummaryBtn) {
        copyRealAiSummaryBtn.addEventListener("click", async () => {
            const originalText = copyRealAiSummaryBtn.textContent;
            const summary = buildLaudoSummary();
            try {
                await navigator.clipboard.writeText(summary);
                copyRealAiSummaryBtn.textContent = "📋 Resumo copiado!";
                setTimeout(() => copyRealAiSummaryBtn.textContent = originalText, 1600);
            } catch (error) {
                copyRealAiSummaryBtn.textContent = "Erro ao copiar";
                setTimeout(() => copyRealAiSummaryBtn.textContent = originalText, 1600);
            }
        });
    }

    // Helper formatting functions
    function capitalizeFirstLetter(string) {
        if (!string) return "";
        return string.charAt(0).toUpperCase() + string.slice(1);
    }

    function formatSiteType(type) {
        const types = {
            "proprio": "Site próprio",
            "site_proprio": "Site próprio",
            "generico": "Site terceirizado",
            "site_terceirizado": "Site terceirizado",
            "cardapio_plataforma_externa": "Cardápio/plataforma externa",
            "nao_encontrado": "Não Encontrado",
            "incerto": "Incerto",
            "rede_social": "Rede social"
        };
        return types[type] || capitalizeFirstLetter(type);
    }

    function formatInstagramLinkType(type) {
        const types = {
            "dominio_proprio": "Domínio próprio",
            "linktree_ou_similar": "Linktree/Beacons/similar",
            "whatsapp_direto": "WhatsApp direto",
            "google_sites": "Google Sites",
            "canva_site": "Canva site",
            "wix_ou_similar": "Wix ou similar",
            "cardapio_online_terceirizado": "Cardápio online terceirizado",
            "nao_identificado": "Não identificado"
        };
        return types[type] || capitalizeFirstLetter(String(type || "").replaceAll("_", " "));
    }

    function renderLaudoBadges(data) {
        if (!realAiBadges) return;
        const badges = [];
        const compat = String(data.compatibilidade_whatsapp || "incerto").toLowerCase();
        const tipoSite = String(data.tipo_site || "incerto").toLowerCase();
        const aprovado = String(data.lead_aprovado_abordagem || "com_ressalvas").toLowerCase();

        if (compat === "compativel") badges.push({ label: "WhatsApp compatível", tone: "success" });
        else if (compat === "divergente") badges.push({ label: "WhatsApp divergente", tone: "danger" });
        else badges.push({ label: "WhatsApp incerto", tone: "warn" });

        if (tipoSite === "site_proprio" || tipoSite === "proprio") badges.push({ label: "Site próprio", tone: "success" });
        else if (tipoSite === "site_terceirizado" || tipoSite === "generico") badges.push({ label: "Site terceirizado", tone: "warn" });
        else badges.push({ label: "Sem site próprio", tone: "danger" });

        if (aprovado === "sim") badges.push({ label: "Lead aprovado", tone: "success" });
        else if (aprovado === "nao") badges.push({ label: "Possível lead ruim", tone: "danger" });
        else badges.push({ label: "Lead com ressalvas", tone: "warn" });

        realAiBadges.innerHTML = badges.map(b => `<span class=\"laudo-badge ${b.tone}\">${b.label}</span>`).join("");
    }

    function buildLaudoSummary() {
        return [
            `Laudo do Lead: ${realAiLeadName?.textContent || "-"}`,
            `Score: ${realAiScore?.textContent || "0/100"}`,
            `Empresa: ${realAiExiste?.textContent || "Incerto"} | Atividade: ${realAiAtividade?.textContent || "Incerto"} | Status: ${realAiStatusProvavel?.textContent || "Incerto"}`,
            `WhatsApp: ${realAiWhatsCompat?.textContent || "Incerto"} (${realAiWhatsConfianca?.textContent || "Baixa"})`,
            `Instagram: ${realAiInstagramEncontrado?.textContent || "Incerto"} | Link na bio: ${realAiInstagramLink?.textContent || "Incerto"} | Tipo: ${realAiInstagramTipoLink?.textContent || "Não identificado"}`,
            `Site: ${realAiSiteEncontrado?.textContent || "Incerto"} | Tipo: ${realAiTipoSite?.textContent || "Incerto"} | Qualidade: ${realAiQualidadeSite?.textContent || "Incerta"}`,
            `Decisão: ${realAiAprovado?.textContent || "Com ressalvas"} | Prioridade: ${realAiPrioridade?.textContent || "Média"}`,
            `Motivo prioridade: ${realAiMotivoPrioridade?.textContent || "-"}`,
            `Próximo passo: ${realAiProximoPasso?.textContent || "-"}`,
            `Oferta: ${realAiOferta?.textContent || "-"}`,
            `Mensagem abordagem: ${realAiMessageText?.value || "-"}`
        ].join("\\n");
    }

    // -------------------------------------------------------------
    // 5. Apify API Connection Tester
    // -------------------------------------------------------------
    const btnTestApify = document.getElementById("btnTestApify");
    const apifyTestStatus = document.getElementById("apifyTestStatus");

    if (btnTestApify) {
        btnTestApify.addEventListener("click", async () => {
            btnTestApify.disabled = true;
            btnTestApify.textContent = "🔌 Conectando à API do Apify...";
            apifyTestStatus.classList.add("hidden");

            try {
                const response = await fetch("/api/apify/test-connection", {
                    method: "POST"
                });
                const result = await response.json();

                apifyTestStatus.classList.remove("hidden");
                if (response.ok && result.ok) {
                    apifyTestStatus.style.background = "rgba(16, 185, 129, 0.15)";
                    apifyTestStatus.style.border = "1px solid rgba(16, 185, 129, 0.3)";
                    apifyTestStatus.style.color = "#a7f3d0";
                    apifyTestStatus.textContent = result.message;
                    showToast("Conexão com Apify estabelecida!", "info");
                } else {
                    apifyTestStatus.style.background = "rgba(239, 68, 68, 0.15)";
                    apifyTestStatus.style.border = "1px solid rgba(239, 68, 68, 0.3)";
                    apifyTestStatus.style.color = "#fecaca";
                    apifyTestStatus.textContent = result.message || "Erro desconhecido ao testar token.";
                    showToast(result.message || "Erro ao conectar com Apify.", "error");
                }
            } catch (error) {
                apifyTestStatus.classList.remove("hidden");
                apifyTestStatus.style.background = "rgba(239, 68, 68, 0.15)";
                apifyTestStatus.style.border = "1px solid rgba(239, 68, 68, 0.3)";
                apifyTestStatus.style.color = "#fecaca";
                apifyTestStatus.textContent = "Falha de comunicação ou de rede ao testar API.";
                showToast("Erro de conexão ao testar Apify.", "error");
            } finally {
                btnTestApify.disabled = false;
                btnTestApify.textContent = "🔌 Testar Conexão com Apify";
            }
        });
    }
});
