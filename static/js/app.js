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
        // Change "Analisar com IA" button text
        const aiBtn = card.querySelector(".run-ai-btn");
        if (aiBtn) {
            aiBtn.textContent = "🪄 Ver Análise IA";
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
            <span class="ai-box-title">🤖 Insight da Inteligência Artificial:</span>
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
    // 3. Google Places API Search Results Flow
    // -------------------------------------------------------------
    const googlePlacesForm = document.getElementById("googlePlacesForm");
    const placesResults = document.getElementById("placesResults");
    const placesStatus = document.getElementById("placesStatus");
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

            setPlacesStatus("🔍 Buscando empresas reais no Google Places...", "info");
            placesResults.innerHTML = "";
            resultsToolbar.classList.add("hidden");

            try {
                const response = await fetch("/api/google-places/buscar", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                const data = await response.json();

                if (!response.ok || !data.ok) {
                    foundLeads = [];
                    setPlacesStatus(data.message || "Não foi possível concluir a busca.", "error");
                    return;
                }

                foundLeads = data.leads || [];
                renderPlacesResults(foundLeads, data.message);
            } catch (error) {
                foundLeads = [];
                setPlacesStatus("Erro inesperado ao buscar leads. Verifique a conexão e tente novamente.", "error");
            }
        });
    }

    if (saveAllButton) {
        saveAllButton.addEventListener("click", async () => {
            if (!foundLeads.length) return;
            
            saveAllButton.disabled = true;
            saveAllButton.textContent = "Salvando...";
            const result = await postJson("/api/google-places/salvar-todos", { leads: foundLeads });
            
            setPlacesStatus(result.message || "Leads processados.", result.ok ? "success" : "error");
            saveAllButton.textContent = "💾 Importar Todos no CRM";
            saveAllButton.disabled = false;
        });
    }

    function renderPlacesResults(leads, message) {
        placesResults.innerHTML = "";

        if (!leads.length) {
            setPlacesStatus(message || "Nenhum lead encontrado para essa busca.", "info");
            return;
        }

        hidePlacesStatus();
        resultsToolbar.classList.remove("hidden");
        resultsCount.textContent = `${leads.length} lead(s) encontrado(s)`;
        resultsMessage.textContent = message || "";

        leads.forEach((lead, index) => {
            const card = document.createElement("article");
            card.className = `lead-card potential-${priorityClass(lead.prioridade)}`;
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
                    <button class="primary-button save-found-lead" type="button" data-index="${index}">💾 Salvar no CRM</button>
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
        
        const result = await postJson("/api/google-places/salvar", { lead });
        
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
    
    const realAiLeadName = document.getElementById("realAiLeadName");
    const realAiDate = document.getElementById("realAiDate");
    const realAiScore = document.getElementById("realAiScore");
    const realAiExiste = document.getElementById("realAiExiste");
    const realAiSiteEncontrado = document.getElementById("realAiSiteEncontrado");
    const realAiTipoSite = document.getElementById("realAiTipoSite");
    const realAiPresenca = document.getElementById("realAiPresenca");
    const realAiReasonText = document.getElementById("realAiReasonText");
    const realAiProblema = document.getElementById("realAiProblema");
    const realAiOferta = document.getElementById("realAiOferta");
    const realAiPreco = document.getElementById("realAiPreco");
    const realAiPotentialBadge = document.getElementById("realAiPotentialBadge");
    const realAiMessageText = document.getElementById("realAiMessageText");
    
    const copyRealAiMessageBtn = document.getElementById("copyRealAiMessage");
    const sendRealAiWhatsappBtn = document.getElementById("sendRealAiWhatsapp");
    const realAiSourcesSection = document.getElementById("realAiSourcesSection");
    const realAiSourcesList = document.getElementById("realAiSourcesList");
    const reanalyzeRealAiBtn = document.getElementById("reanalyzeRealAiBtn");

    let currentRealAiLeadCard = null;

    document.addEventListener("click", async (event) => {
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
                    showToast(errMsg, "error");
                    realAiModal.classList.add("hidden");
                }
            }, delay);
        } catch (error) {
            clearInterval(stepInterval);
            showToast("Falha de conexão ao acessar IA real.", "error");
            realAiModal.classList.add("hidden");
        }
    }

    function showRealAiLoading() {
        realAiLoading.classList.remove("hidden");
        realAiResults.classList.add("hidden");
        reanalyzeRealAiBtn.style.display = "none";
    }

    function showRealAiResults(result, card) {
        realAiLoading.classList.add("hidden");
        realAiResults.classList.remove("hidden");
        reanalyzeRealAiBtn.style.display = "inline-flex";

        const data = result.data;

        // Header and Date
        realAiDate.textContent = `Analisado em: ${result.analisado_em || 'Recente'}`;
        realAiScore.textContent = `${result.score || 0}/100`;

        // 4 metrics grid
        realAiExiste.textContent = capitalizeFirstLetter(data.empresa_existe || "incerto");
        realAiSiteEncontrado.textContent = capitalizeFirstLetter(data.site_encontrado || "incerto");
        realAiTipoSite.textContent = formatSiteType(data.tipo_site || "incerto");
        realAiPresenca.textContent = capitalizeFirstLetter(data.presenca_digital || "incerto");

        // Sections
        realAiReasonText.textContent = data.diagnostico || "Sem diagnóstico disponível.";
        realAiProblema.textContent = data.problema_detectado || "Nenhum detectado.";
        realAiOferta.textContent = data.oferta_recomendada || "Nenhuma sugestão.";
        realAiPreco.textContent = data.preco_sugerido || "Sob consulta";

        // Potential Badge
        const potencial = result.potencial || "baixo";
        realAiPotentialBadge.textContent = `Potencial ${capitalizeFirstLetter(potencial)}`;
        realAiPotentialBadge.className = `potential-badge ${priorityClass(potencial)}`;

        // Message
        realAiMessageText.value = data.mensagem_whatsapp || "";

        // WhatsApp trigger configuration
        const tel = card.dataset.telefone || "";
        if (sendRealAiWhatsappBtn) {
            if (tel) {
                // Remove non-digit chars
                const cleanPhone = tel.replace(/\D/g, "");
                sendRealAiWhatsappBtn.setAttribute("href", `https://wa.me/${cleanPhone}?text=${encodeURIComponent(data.mensagem_whatsapp || "")}`);
                sendRealAiWhatsappBtn.style.display = "inline-flex";
            } else {
                sendRealAiWhatsappBtn.style.display = "none";
            }
        }

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

    function updateCardUiAfterRealAnalysis(card, result) {
        // Update "Pesquisar com IA real" button text
        const realBtn = card.querySelector(".run-real-ai-btn");
        if (realBtn) {
            realBtn.textContent = "🌐 Ver IA Real";
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
        const truncatedMotivo = result.data.diagnostico.length > 140 ? result.data.diagnostico.slice(0, 137) + "..." : result.data.diagnostico;
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
            <span class="ai-box-title" style="color: #c084fc;">🌐 Insight da IA Real:</span>
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

    // Helper formatting functions
    function capitalizeFirstLetter(string) {
        if (!string) return "";
        return string.charAt(0).toUpperCase() + string.slice(1);
    }

    function formatSiteType(type) {
        const types = {
            "proprio": "Site Próprio",
            "generico": "Site Genérico",
            "rede_social": "Apenas Redes Sociais",
            "nao_encontrado": "Não Encontrado",
            "incerto": "Incerto"
        };
        return types[type] || capitalizeFirstLetter(type);
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
