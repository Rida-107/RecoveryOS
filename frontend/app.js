/* ============================================================
   RecoveryOS — AI Revenue Recovery Agent
   Frontend v1.1
   ============================================================ */

"use strict";

/* ============================================================
   GLOBAL STATE
   ============================================================ */

let payments = [];
let auditEvents = [];
let metricsData = null;


/* ============================================================
   DOM HELPERS
   ============================================================ */

function $(id) {
    return document.getElementById(id);
}


function setText(id, value) {
    const element = $(id);

    if (element) {
        element.textContent = value;
    }
}


function setWidth(id, value) {
    const element = $(id);

    if (!element) {
        return;
    }

    const percentage = Math.max(
        0,
        Math.min(
            100,
            Number(value) || 0
        )
    );

    element.style.width =
        `${percentage}%`;
}


function escapeHTML(value) {

    if (
        value === null ||
        value === undefined
    ) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


/* ============================================================
   FORMATTING
   ============================================================ */

function formatINR(value) {

    const number =
        Number(value) || 0;

    return new Intl.NumberFormat(
        "en-IN",
        {
            style: "currency",
            currency: "INR",
            maximumFractionDigits: 0
        }
    ).format(number);
}


function formatPercent(value) {

    const number =
        Number(value) || 0;

    return (
        number * 100
    ).toFixed(2) + "%";
}


function formatDate(value) {

    if (!value) {
        return "—";
    }

    try {

        return new Date(value)
            .toLocaleString(
                "en-IN",
                {
                    dateStyle: "medium",
                    timeStyle: "short"
                }
            );

    } catch {

        return String(value);
    }
}


function actionLabel(action) {

    const labels = {

        "PAYMENT_LINK":
            "Payment Link",

        "DELAYED_RETRY":
            "Delayed Retry",

        "HUMAN_REVIEW":
            "Human Review"
    };

    return (
        labels[action] ||
        action ||
        "—"
    );
}


/* ============================================================
   API
   ============================================================ */

async function apiGet(endpoint) {

    const response =
        await fetch(endpoint, {
            cache: "no-store"
        });

    if (!response.ok) {

        let message =
            `Request failed: ${response.status}`;

        try {

            const data =
                await response.json();

            if (data.detail) {
                message =
                    data.detail;
            }

        } catch {
            // Ignore JSON parsing failure.
        }

        throw new Error(message);
    }

    return response.json();
}


async function apiPost(
    endpoint,
    body
) {

    const response =
        await fetch(
            endpoint,
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify(body)
            }
        );

    if (!response.ok) {

        let message =
            `Request failed: ${response.status}`;

        try {

            const data =
                await response.json();

            if (data.detail) {
                message =
                    data.detail;
            }

        } catch {
            // Ignore JSON parsing failure.
        }

        throw new Error(message);
    }

    return response.json();
}


/* ============================================================
   NAVIGATION
   ============================================================ */

function showPage(pageName) {

    const pages = {
        overview:
            "page-overview",

        opportunities:
            "page-opportunities",

        agent:
            "page-agent",

        audit:
            "page-audit"
    };


    Object.values(pages)
        .forEach(id => {

            const section = $(id);

            if (section) {
                section.classList.remove(
                    "active"
                );
            }
        });


    const target =
        $(pages[pageName]);

    if (target) {
        target.classList.add(
            "active"
        );
    }


    document
        .querySelectorAll(
            ".nav-btn"
        )
        .forEach(button => {

            button.classList.toggle(
                "active",
                button.dataset.page === pageName
            );
        });


    const titles = {

        overview: [
            "Recovery Overview",
            "AI-powered revenue recovery performance"
        ],

        opportunities: [
            "Recovery Opportunities",
            "Prioritized failed payments by expected recovery value"
        ],

        agent: [
            "Agent Console",
            "Run and inspect a RecoveryOS decision"
        ],

        audit: [
            "Audit Trail",
            "Transparent record of every recovery decision"
        ]
    };


    const title =
        titles[pageName] ||
        titles.overview;


    setText(
        "page-title",
        title[0]
    );

    setText(
        "page-subtitle",
        title[1]
    );


    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}


function setupNavigation() {

    document
        .querySelectorAll(
            ".nav-btn"
        )
        .forEach(button => {

            button.addEventListener(
                "click",
                event => {

                    event.preventDefault();

                    const page =
                        button.dataset.page;

                    if (page) {
                        showPage(page);
                    }
                }
            );
        });


    document
        .querySelectorAll(
            "[onclick=\"showPage('opportunities')\"]"
        )
        .forEach(button => {

            button.addEventListener(
                "click",
                event => {

                    event.preventDefault();

                    showPage(
                        "opportunities"
                    );
                }
            );
        });
}


/* ============================================================
   HEALTH
   ============================================================ */

async function checkHealth() {

    try {

        const data =
            await apiGet(
                "/health"
            );


        console.log(
            "RecoveryOS health:",
            data
        );


        const livePill =
            document.querySelector(
                ".live-pill"
            );


        if (livePill) {

            livePill.innerHTML = `
                <span class="live-dot"></span>
                Live
            `;
        }


        const version =
            document.querySelector(
                ".sidebar-footer div:last-child"
            );


        if (version) {
            version.textContent =
                `v${data.version || "1.0.0"}`;
        }


    } catch (error) {

        console.error(
            "Health check failed:",
            error
        );
    }
}


/* ============================================================
   METRICS
   ============================================================ */

function getRecoveryOSStrategy() {

    if (!metricsData) {
        return {};
    }

    return (
        metricsData.strategies?.RecoveryOS ||
        {}
    );
}


function getRuleBasedStrategy() {

    if (!metricsData) {
        return {};
    }

    return (
        metricsData.strategies?.[
            "Rule Based"
        ] ||
        {}
    );
}


function getAlwaysRetryStrategy() {

    if (!metricsData) {
        return {};
    }

    return (
        metricsData.strategies?.[
            "Always Retry"
        ] ||
        {}
    );
}


function renderMetrics() {

    if (!metricsData) {
        return;
    }


    /*
       Current backend structure:

       {
           dataset_records,
           total_payment_value,
           strategies: {
               "Always Retry": {...},
               "Rule Based": {...},
               "RecoveryOS": {...}
           },
           recoveryos_improvement: {...},
           safety: {...}
       }
    */


    const recoveryOS =
        getRecoveryOSStrategy();

    const ruleBased =
        getRuleBasedStrategy();

    const alwaysRetry =
        getAlwaysRetryStrategy();


    const totalValue =
        Number(
            metricsData.total_payment_value
        ) || 0;


    const recovered =
        Number(
            recoveryOS.expected_recovery
        ) || 0;


    const recoveryRate =
        Number(
            recoveryOS.recovery_rate
        ) || 0;


    const ruleRate =
        Number(
            ruleBased.recovery_rate
        ) || 0;


    const alwaysRate =
        Number(
            alwaysRetry.recovery_rate
        ) || 0;


    const improvement =
        Number(
            metricsData
                .recoveryos_improvement
                ?.vs_rule_based
                ?.relative_improvement
        ) || 0;


    const recoveryOSActions =
        recoveryOS.actions ||
        {};


    const automated =
        Number(
            recoveryOSActions.PAYMENT_LINK ||
            0
        ) +
        Number(
            recoveryOSActions.DELAYED_RETRY ||
            0
        );


    const human =
        Number(
            recoveryOSActions.HUMAN_REVIEW ||
            0
        );


    const totalActions =
        automated +
        human;


    const automationRate =
        totalActions > 0
            ? automated / totalActions
            : 0;


    const humanRate =
        totalActions > 0
            ? human / totalActions
            : 0;


    /* -----------------------------
       KPI CARDS
       ----------------------------- */

    setText(
        "revenue-at-risk",
        formatINR(totalValue)
    );


    setText(
        "revenue-recovered",
        formatINR(recovered)
    );


    setText(
        "recovery-rate",
        formatPercent(recoveryRate)
    );


    setText(
        "revenue-uplift",
        `+${(improvement * 100).toFixed(2)}%`
    );


    setText(
        "automation-rate",
        formatPercent(automationRate)
    );


    setText(
        "human-review",
        formatPercent(humanRate)
    );


    /* -----------------------------
       PERFORMANCE
       ----------------------------- */

    setText(
        "baseline-rate",
        formatPercent(ruleRate)
    );


    setText(
        "recoveryos-rate",
        formatPercent(recoveryRate)
    );


    setWidth(
        "baseline-bar",
        ruleRate * 100
    );


    setWidth(
        "recoveryos-bar",
        recoveryRate * 100
    );


    /* -----------------------------
       ACTION DISTRIBUTION
       ----------------------------- */

    renderActionDistribution();


    /* -----------------------------
       TOP OPPORTUNITIES
       ----------------------------- */

    renderOpportunityPreview();


    console.log(
        "RecoveryOS metrics loaded:",
        metricsData
    );
}


/* ============================================================
   ACTION DISTRIBUTION
   ============================================================ */

function renderActionDistribution() {

    const container =
        $("action-distribution");


    if (!container) {
        return;
    }


    const recoveryOS =
        getRecoveryOSStrategy();


    const actions =
        recoveryOS.actions ||
        {};


    const paymentLink =
        Number(
            actions.PAYMENT_LINK
        ) || 0;


    const delayedRetry =
        Number(
            actions.DELAYED_RETRY
        ) || 0;


    const humanReview =
        Number(
            actions.HUMAN_REVIEW
        ) || 0;


    const total =
        paymentLink +
        delayedRetry +
        humanReview;


    if (total <= 0) {

        container.innerHTML = `
            <div class="empty-state">
                No strategy distribution available.
            </div>
        `;

        return;
    }


    const rows = [

        [
            "Payment Link",
            paymentLink
        ],

        [
            "Delayed Retry",
            delayedRetry
        ],

        [
            "Human Review",
            humanReview
        ]
    ];


    container.innerHTML =
        rows
            .map(
                ([label, count]) => {

                    const percentage =
                        (
                            count /
                            total
                        ) * 100;


                    return `
                        <div class="action-row">

                            <div class="action-top">

                                <span>
                                    ${escapeHTML(label)}
                                </span>

                                <strong>
                                    ${percentage.toFixed(1)}%
                                </strong>

                            </div>

                            <div class="progress-track">

                                <div
                                    class="progress-fill"
                                    style="
                                        width:${percentage}%;
                                    "
                                ></div>

                            </div>

                        </div>
                    `;
                }
            )
            .join("");
}


/* ============================================================
   OPPORTUNITIES
   ============================================================ */

function opportunityRow(payment) {

    const probability =
        Number(
            payment.recovery_probability
        ) || 0;


    const expectedValue =
        Number(
            payment.expected_recovery_value
        ) || 0;


    const action =
        payment.recommended_action ||
        "HUMAN_REVIEW";


    return `
        <tr>

            <td>
                <button
                    class="payment-id-button"
                    data-payment-id="${escapeHTML(
                        payment.payment_id
                    )}"
                >
                    ${escapeHTML(
                        payment.payment_id
                    )}
                </button>
            </td>

            <td>
                ${formatINR(
                    payment.amount
                )}
            </td>

            <td>
                ${escapeHTML(
                    payment.failure_code ||
                    "—"
                )}
            </td>

            <td>
                ${formatPercent(
                    probability
                )}
            </td>

            <td>
                <strong>
                    ${formatINR(
                        expectedValue
                    )}
                </strong>
            </td>

            <td>
                <span class="status-pill">
                    ${escapeHTML(
                        actionLabel(action)
                    )}
                </span>
            </td>

        </tr>
    `;
}


function renderOpportunityPreview() {

    const table =
        $("opportunity-preview");


    if (!table) {
        return;
    }


    const topPayments =
        [...payments]
            .sort(
                (a, b) =>
                    Number(
                        b.expected_recovery_value ||
                        0
                    ) -
                    Number(
                        a.expected_recovery_value ||
                        0
                    )
            )
            .slice(0, 5);


    if (!topPayments.length) {

        table.innerHTML = `
            <tr>
                <td
                    colspan="6"
                    class="empty-state"
                >
                    No recovery opportunities available.
                </td>
            </tr>
        `;

        return;
    }


    table.innerHTML =
        topPayments
            .map(
                opportunityRow
            )
            .join("");


    attachPaymentButtons(
        table
    );
}


function renderAllOpportunities() {

    const table =
        $("opportunities-table");


    if (!table) {
        return;
    }


    if (!payments.length) {

        table.innerHTML = `
            <tr>
                <td
                    colspan="7"
                    class="empty-state"
                >
                    No recovery opportunities available.
                </td>
            </tr>
        `;

        return;
    }


    table.innerHTML =
        [...payments]
            .sort(
                (a, b) =>
                    Number(
                        b.expected_recovery_value ||
                        0
                    ) -
                    Number(
                        a.expected_recovery_value ||
                        0
                    )
            )
            .map(payment => `

                <tr>

                    <td>
                        <button
                            class="payment-id-button"
                            data-payment-id="${escapeHTML(
                                payment.payment_id
                            )}"
                        >
                            ${escapeHTML(
                                payment.payment_id
                            )}
                        </button>
                    </td>

                    <td>
                        ${formatINR(
                            payment.amount
                        )}
                    </td>

                    <td>
                        ${escapeHTML(
                            payment.payment_method ||
                            "—"
                        )}
                    </td>

                    <td>
                        ${escapeHTML(
                            payment.failure_code ||
                            "—"
                        )}
                    </td>

                    <td>
                        ${formatPercent(
                            payment.recovery_probability
                        )}
                    </td>

                    <td>
                        <strong>
                            ${formatINR(
                                payment.expected_recovery_value
                            )}
                        </strong>
                    </td>

                    <td>
                        ${escapeHTML(
                            actionLabel(
                                payment.recommended_action
                            )
                        )}
                    </td>

                </tr>

            `)
            .join("");


    attachPaymentButtons(
        table
    );
}


function attachPaymentButtons(container) {

    container
        .querySelectorAll(
            ".payment-id-button"
        )
        .forEach(button => {

            button.addEventListener(
                "click",
                () => {

                    const paymentId =
                        button.dataset.paymentId;

                    if (!paymentId) {
                        return;
                    }


                    setText(
                        "payment-id",
                        paymentId
                    );


                    const input =
                        $("payment-id");


                    if (input) {
                        input.value =
                            paymentId;
                    }


                    showPage(
                        "agent"
                    );
                }
            );
        });
}


/* ============================================================
   LOAD PAYMENTS
   ============================================================ */

async function loadPayments() {

    const data =
        await apiGet(
            "/payments?limit=100"
        );


    payments =
        data.payments ||
        [];


    renderOpportunityPreview();

    renderAllOpportunities();


    console.log(
        "Recovery opportunities loaded:",
        payments.length
    );
}


/* ============================================================
   AUDIT
   ============================================================ */

async function loadAudit() {

    const data =
        await apiGet(
            "/audit?limit=100"
        );


    auditEvents =
        data.events ||
        [];


    renderAudit();


    console.log(
        "Audit events loaded:",
        auditEvents.length
    );
}


function renderAudit() {

    const table =
        $("audit-table");


    if (!table) {
        return;
    }


    if (!auditEvents.length) {

        table.innerHTML = `
            <tr>
                <td
                    colspan="8"
                    class="empty-state"
                >
                    No audit events yet.
                </td>
            </tr>
        `;

        return;
    }


    table.innerHTML =
        auditEvents
            .map(event => {

                return `

                    <tr>

                        <td>
                            ${escapeHTML(
                                event.audit_id ||
                                "—"
                            )}
                        </td>

                        <td>
                            ${escapeHTML(
                                event.payment_id ||
                                "—"
                            )}
                        </td>

                        <td>
                            ${formatINR(
                                event.amount
                            )}
                        </td>

                        <td>
                            ${escapeHTML(
                                event.failure_code ||
                                "—"
                            )}
                        </td>

                        <td>
                            ${escapeHTML(
                                actionLabel(
                                    event.selected_action ||
                                    event.action
                                )
                            )}
                        </td>

                        <td>
                            ${escapeHTML(
                                event.execution_status ||
                                event.execution?.status ||
                                "—"
                            )}
                        </td>

                        <td>
                            ${escapeHTML(
                                event.verification_status ||
                                event.verification?.status ||
                                "—"
                            )}
                        </td>

                        <td>
                            ${formatDate(
                                event.created_at ||
                                event.timestamp
                            )}
                        </td>

                    </tr>
                `;
            })
            .join("");
}


async function refreshAudit() {

    try {

        await loadAudit();

    } catch (error) {

        console.error(
            "Audit refresh failed:",
            error
        );
    }
}


/* ============================================================
   AGENT CONSOLE
   ============================================================ */

async function runRecovery() {

    const input =
        $("payment-id");


    const button =
        $("run-agent");


    const errorBox =
        $("agent-error");


    const resultPanel =
        $("agent-result");


    if (!input) {

        console.error(
            "RecoveryOS: payment-id input not found."
        );

        return;
    }


    const paymentId =
        input.value.trim();


    if (!paymentId) {

        showAgentError(
            "Enter a payment ID first."
        );

        return;
    }


    if (errorBox) {

        errorBox.textContent =
            "";

        errorBox.style.display =
            "none";
    }


    if (resultPanel) {

        resultPanel.innerHTML =
            "";

        resultPanel.style.display =
            "none";
    }


    if (button) {

        button.disabled =
            true;

        button.dataset.originalText =
            button.textContent;

        button.textContent =
            "Running RecoveryOS...";
    }


    updateTraceLoading();


    console.log(
        "RecoveryOS: starting recovery for",
        paymentId
    );


    try {

        const response =
            await apiPost(
                "/recover",
                {
                    payment_id:
                        paymentId
                }
            );


        console.log(
            "RecoveryOS: /recover response:",
            response
        );


        renderAgentResult(
            response
        );


        renderAgentTrace(
            response.agent ||
            {}
        );


        await refreshAudit();


    } catch (error) {

        console.error(
            "RecoveryOS recovery failed:",
            error
        );


        showAgentError(
            error.message ||
            "Recovery request failed."
        );


        showTraceError(
            error.message
        );


    } finally {

        if (button) {

            button.disabled =
                false;

            button.textContent =
                button.dataset.originalText ||
                "Run Recovery";
        }
    }
}


/* ============================================================
   AGENT ERROR
   ============================================================ */

function showAgentError(message) {

    const box =
        $("agent-error");


    if (!box) {

        alert(message);

        return;
    }


    box.textContent =
        message;


    box.style.display =
        "block";


    box.classList.remove(
        "hidden"
    );
}


/* ============================================================
   AGENT RESULT
   ============================================================ */

function renderAgentResult(response) {

    const panel =
        $("agent-result");


    if (!panel) {
        return;
    }


    const agent =
        response.agent ||
        {};


    const payment =
        agent.payment ||
        {};


    const prediction =
        agent.ml_prediction ||
        {};


    const diagnosis =
        agent.llm_diagnosis ||
        {};


    const decision =
        agent.decision ||
        {};


    const execution =
        agent.execution ||
        {};


    const verification =
        agent.verification ||
        {};


    const audit =
        agent.audit ||
        agent.audit_event ||
        {};


    const probabilities =
        agent.action_probabilities ||
        {};


    panel.innerHTML = `

        <div class="result-content">

            <div class="result-header">

                <div>
                    <div class="result-title">
                        RecoveryOS Decision
                    </div>

                    <div class="result-subtitle">
                        Controlled recovery decision completed
                    </div>
                </div>

            </div>


            <div class="result-grid">

                <div class="result-stat">

                    <span>
                        Payment
                    </span>

                    <strong>
                        ${escapeHTML(
                            payment.payment_id ||
                            "—"
                        )}
                    </strong>

                </div>


                <div class="result-stat">

                    <span>
                        Amount
                    </span>

                    <strong>
                        ${formatINR(
                            payment.amount
                        )}
                    </strong>

                </div>


                <div class="result-stat">

                    <span>
                        Failure
                    </span>

                    <strong>
                        ${escapeHTML(
                            payment.failure_code ||
                            "—"
                        )}
                    </strong>

                </div>


                <div class="result-stat">

                    <span>
                        Base Probability
                    </span>

                    <strong>
                        ${formatPercent(
                            prediction.base_recovery_probability
                        )}
                    </strong>

                </div>


                <div class="result-stat">

                    <span>
                        Selected Action
                    </span>

                    <strong>
                        ${escapeHTML(
                            actionLabel(
                                decision.selected_action
                            )
                        )}
                    </strong>

                </div>


                <div class="result-stat">

                    <span>
                        Action Probability
                    </span>

                    <strong>
                        ${formatPercent(
                            decision.selected_probability
                        )}
                    </strong>

                </div>


                <div class="result-stat">

                    <span>
                        Expected Recovery
                    </span>

                    <strong>
                        ${formatINR(
                            decision.expected_recovery_value
                        )}
                    </strong>

                </div>


                <div class="result-stat">

                    <span>
                        Execution
                    </span>

                    <strong>
                        ${escapeHTML(
                            execution.status ||
                            "—"
                        )}
                    </strong>

                </div>


                <div class="result-stat">

                    <span>
                        Verification
                    </span>

                    <strong>
                        ${escapeHTML(
                            verification.status ||
                            "—"
                        )}
                    </strong>

                </div>


                <div class="result-stat">

                    <span>
                        Audit ID
                    </span>

                    <strong>
                        ${escapeHTML(
                            audit.audit_id ||
                            "—"
                        )}
                    </strong>

                </div>

            </div>


            <div class="result-section">

                <strong>
                    Diagnosis
                </strong>

                <p>
                    ${escapeHTML(
                        diagnosis.diagnosis ||
                        "Diagnosis unavailable."
                    )}
                </p>

            </div>


            <div class="result-section">

                <strong>
                    Decision Reason
                </strong>

                <p>
                    ${escapeHTML(
                        decision.decision_reason ||
                        "Decision reason unavailable."
                    )}
                </p>

            </div>


            <div class="result-section">

                <strong>
                    Action Probabilities
                </strong>

                <p>
                    Delayed Retry:
                    ${formatPercent(
                        probabilities.DELAYED_RETRY
                    )}
                    &nbsp; • &nbsp;

                    Payment Link:
                    ${formatPercent(
                        probabilities.PAYMENT_LINK
                    )}
                    &nbsp; • &nbsp;

                    Human Review:
                    ${formatPercent(
                        probabilities.HUMAN_REVIEW
                    )}
                </p>

            </div>


            <div class="result-section">

                <strong>
                    Verification
                </strong>

                <p>
                    ${escapeHTML(
                        verification.message ||
                        verification.status ||
                        "Verification completed."
                    )}
                </p>

            </div>

        </div>
    `;


    panel.style.display =
        "block";


    panel.classList.remove(
        "hidden"
    );
}


/* ============================================================
   AGENT TRACE
   ============================================================ */

function updateTraceLoading() {

    const container =
        $("agent-trace");


    if (!container) {
        return;
    }


    container.innerHTML = `

        <div class="trace-step">

            <div class="trace-number">
                1
            </div>

            <div>
                <strong>
                    OBSERVE
                </strong>

                <div>
                    Loading failed payment context...
                </div>
            </div>

        </div>


        <div class="trace-step">

            <div class="trace-number">
                2
            </div>

            <div>
                <strong>
                    PREDICT
                </strong>

                <div>
                    Waiting for ML recovery probability...
                </div>
            </div>

        </div>


        <div class="trace-step">

            <div class="trace-number">
                3
            </div>

            <div>
                <strong>
                    DIAGNOSE
                </strong>

                <div>
                    Determining failure reason...
                </div>
            </div>

        </div>


        <div class="trace-step">

            <div class="trace-number">
                4
            </div>

            <div>
                <strong>
                    PLAN
                </strong>

                <div>
                    Comparing recovery strategies...
                </div>
            </div>

        </div>


        <div class="trace-step">

            <div class="trace-number">
                5
            </div>

            <div>
                <strong>
                    POLICY
                </strong>

                <div>
                    Applying deterministic safety controls...
                </div>
            </div>

        </div>


        <div class="trace-step">

            <div class="trace-number">
                6
            </div>

            <div>
                <strong>
                    ACT
                </strong>

                <div>
                    Executing approved recovery tool...
                </div>

            </div>
        </div>


        <div class="trace-step">

            <div class="trace-number">
                7
            </div>

            <div>
                <strong>
                    VERIFY
                </strong>

                <div>
                    Verifying execution outcome...
                </div>

            </div>
        </div>


        <div class="trace-step">

            <div class="trace-number">
                8
            </div>

            <div>
                <strong>
                    AUDIT
                </strong>

                <div>
                    Recording decision and outcome...
                </div>

            </div>
        </div>
    `;
}


function renderAgentTrace(agent) {

    const container =
        $("agent-trace");


    if (!container) {
        return;
    }


    const payment =
        agent.payment ||
        {};


    const prediction =
        agent.ml_prediction ||
        {};


    const diagnosis =
        agent.llm_diagnosis ||
        {};


    const decision =
        agent.decision ||
        {};


    const execution =
        agent.execution ||
        {};


    const verification =
        agent.verification ||
        {};


    const audit =
        agent.audit ||
        agent.audit_event ||
        {};


    const trace = [

        [
            "1",
            "OBSERVE",
            `Loaded ${payment.payment_id || "payment"} with failure ${payment.failure_code || "unknown"}.`
        ],

        [
            "2",
            "PREDICT",
            `ML estimated ${formatPercent(prediction.base_recovery_probability)} base recovery probability.`
        ],

        [
            "3",
            "DIAGNOSE",
            diagnosis.diagnosis ||
            "Failure diagnosis unavailable."
        ],

        [
            "4",
            "PLAN",
            `Selected ${actionLabel(decision.selected_action)} as the preferred recovery strategy.`
        ],

        [
            "5",
            "POLICY",
            decision.decision_reason ||
            "Deterministic policy evaluation completed."
        ],

        [
            "6",
            "ACT",
            execution.message ||
            execution.status ||
            "Recovery tool executed."
        ],

        [
            "7",
            "VERIFY",
            verification.message ||
            verification.status ||
            "Verification completed."
        ],

        [
            "8",
            "AUDIT",
            audit.audit_id
                ? `Decision recorded with audit ID ${audit.audit_id}.`
                : "Decision recorded."
        ]
    ];


    container.innerHTML =
        trace
            .map(
                ([number, title, text]) => `

                    <div class="trace-step">

                        <div class="trace-number">
                            ${number}
                        </div>

                        <div>

                            <strong>
                                ${escapeHTML(title)}
                            </strong>

                            <div>
                                ${escapeHTML(text)}
                            </div>

                        </div>

                    </div>
                `
            )
            .join("");
}


function showTraceError(message) {

    const container =
        $("agent-trace");


    if (!container) {
        return;
    }


    container.innerHTML += `

        <div class="trace-step">

            <div class="trace-number">
                !
            </div>

            <div>

                <strong>
                    Recovery Error
                </strong>

                <div>
                    ${escapeHTML(
                        message ||
                        "Unknown error."
                    )}
                </div>

            </div>

        </div>
    `;
}


/* ============================================================
   REFRESH
   ============================================================ */

async function refreshDashboard() {

    const button =
        $("refresh-btn");


    if (button) {

        button.disabled =
            true;

        button.dataset.originalText =
            button.textContent;

        button.textContent =
            "↻ Loading...";
    }


    try {

        await loadAll();

    } catch (error) {

        console.error(
            "Refresh failed:",
            error
        );

    } finally {

        if (button) {

            button.disabled =
                false;

            button.textContent =
                button.dataset.originalText ||
                "↻ Refresh";
        }
    }
}


/* ============================================================
   LOAD EVERYTHING
   ============================================================ */

async function loadAll() {

    try {

        const [
            metrics,
            paymentData,
            auditData
        ] =
            await Promise.all([

                apiGet(
                    "/metrics"
                ),

                apiGet(
                    "/payments?limit=100"
                ),

                apiGet(
                    "/audit?limit=100"
                )
            ]);


        metricsData =
            metrics;


        payments =
            paymentData.payments ||
            [];


        auditEvents =
            auditData.events ||
            [];


        renderMetrics();

        renderOpportunityPreview();

        renderAllOpportunities();

        renderAudit();


        console.log(
            "RecoveryOS loaded successfully."
        );


    } catch (error) {

        console.error(
            "RecoveryOS loading failed:",
            error
        );


        const actionBox =
            $("action-distribution");


        if (actionBox) {

            actionBox.innerHTML = `
                <div class="empty-state">
                    Unable to load dashboard data.
                    <br>
                    ${escapeHTML(
                        error.message
                    )}
                </div>
            `;
        }
    }
}


/* ============================================================
   AGENT SETUP
   ============================================================ */

function setupAgent() {

    const button =
        $("run-agent");


    const input =
        $("payment-id");


    if (!button) {

        console.error(
            "RecoveryOS ERROR: #run-agent not found."
        );

        return;
    }


    /*
       IMPORTANT:
       Remove any old click handlers by cloning
       the button before attaching our handler.
    */

    const cleanButton =
        button.cloneNode(true);


    button.parentNode.replaceChild(
        cleanButton,
        button
    );


    cleanButton.addEventListener(
        "click",
        event => {

            event.preventDefault();

            runRecovery();
        }
    );


    if (input) {

        input.addEventListener(
            "keydown",
            event => {

                if (
                    event.key ===
                    "Enter"
                ) {

                    event.preventDefault();

                    runRecovery();
                }
            }
        );
    }


    console.log(
        "RecoveryOS: Run Recovery button connected."
    );
}


/* ============================================================
   INITIALIZATION
   ============================================================ */

document.addEventListener(
    "DOMContentLoaded",
    async () => {

        console.log(
            "RecoveryOS frontend starting..."
        );


        setupNavigation();

        setupAgent();


        const refreshButton =
            $("refresh-btn");


        if (refreshButton) {

            refreshButton.addEventListener(
                "click",
                refreshDashboard
            );
        }


        showPage(
            "overview"
        );


        await checkHealth();

        await loadAll();


        console.log(
            "RecoveryOS frontend ready."
        );
    }
);


/* ============================================================
   MAKE showPage AVAILABLE TO HTML
   ============================================================ */

window.showPage =
    showPage;