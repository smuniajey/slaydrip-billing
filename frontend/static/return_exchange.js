let currentInvoice = null;
let soldItems = [];
let newItems = [];

function fetchInvoice() {
    const invoiceInput = document.getElementById("invoice_no");
    const inv = invoiceInput.value.trim();
    resetMessage();
    if (!inv) {
        showMessage("Enter invoice number", true);
        return;
    }

    fetch(`/api/invoice/${encodeURIComponent(inv)}`)
        .then(r => r.json().then(data => ({ ok: r.ok, data })))
        .then(({ ok, data }) => {
            if (!ok) {
                showMessage(data.error || "Invoice not found", true);
                document.getElementById("invoice-summary").classList.add("hidden");
                document.getElementById("items-block").classList.add("hidden");
                document.getElementById("exchange-block").classList.add("hidden");
                currentInvoice = null;
                return;
            }

            currentInvoice = data.sale;
            soldItems = data.items || [];
            renderInvoiceSummary();
            renderSoldItems();
            document.getElementById("exchange-block").classList.remove("hidden");
        })
        .catch(() => showMessage("Error fetching invoice", true));
}

function renderInvoiceSummary() {
    const s = currentInvoice;
    document.getElementById("invoice-summary").classList.remove("hidden");
    document.getElementById("items-block").classList.remove("hidden");
    document.getElementById("sum-name").innerText = s.customer_name;
    document.getElementById("sum-phone").innerText = s.phone;
    document.getElementById("sum-invoice").innerText = s.invoice_no;
    document.getElementById("sum-date").innerText = s.bill_date ? new Date(s.bill_date).toLocaleDateString() : "";
    document.getElementById("sum-mode").innerText = s.payment_mode;
}

function renderSoldItems() {
    const tbody = document.getElementById("sold-body");
    tbody.innerHTML = "";
    soldItems.forEach((item, idx) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${item.design_code} | ${item.product_name} | ${item.color}</td>
            <td>${item.size}</td>
            <td>${item.sold_qty}</td>
            <td>${item.already_returned}</td>
            <td>${item.returnable}</td>
            <td><input type="number" min="0" max="${item.returnable}" value="0" data-idx="${idx}" class="return-input" style="width:80px;"></td>
        `;
        tbody.appendChild(tr);
    });
}

function collectReturnItems() {
    const inputs = document.querySelectorAll(".return-input");
    const items = [];
    inputs.forEach(input => {
        const qty = parseInt(input.value || 0, 10);
        if (qty > 0) {
            const item = soldItems[parseInt(input.dataset.idx, 10)];
            if (qty > item.returnable) {
                throw new Error(`Qty exceeds available for ${item.design_code} ${item.size}`);
            }
            items.push({
                design_id: item.design_id,
                size: item.size,
                quantity: qty
            });
        }
    });
    return items;
}

function submitReturn() {
    resetMessage();
    if (!currentInvoice) {
        showMessage("Fetch an invoice first", true);
        return;
    }
    const payment = document.getElementById("return-payment").value;
    if (!payment) {
        showMessage("Select payment mode", true);
        return;
    }

    let items;
    try {
        items = collectReturnItems();
    } catch (err) {
        showMessage(err.message, true);
        return;
    }

    if (items.length === 0) {
        showMessage("Enter return quantities", true);
        return;
    }

    fetch("/api/returns", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            invoice_no: currentInvoice.invoice_no,
            payment_mode: payment,
            items
        })
    })
    .then(r => r.json().then(data => ({ ok: r.ok, data })))
    .then(({ ok, data }) => {
        if (!ok) throw new Error(data.error || "Return failed");
        showMessage(`Return created. Ref ${data.return_ref}. Refund ₹${data.total_refund.toFixed(2)}`);
        fetchInvoice();
    })
    .catch(err => showMessage(err.message, true));
}

function addNewItem() {
    resetMessage();
    const designSel = document.getElementById("new-design");
    const sizeSel = document.getElementById("new-size");
    const qtyInput = document.getElementById("new-qty");
    const priceInput = document.getElementById("new-price");

    const designId = parseInt(designSel.value || 0, 10);
    const size = sizeSel.value;
    const qty = parseInt(qtyInput.value || 0, 10);
    const price = parseFloat(priceInput.value || 0);

    if (!designId || !size || qty <= 0) {
        showMessage("Select design, size and qty", true);
        return;
    }
    if (Number.isNaN(price)) {
        showMessage("Price missing for design", true);
        return;
    }

    newItems.push({
        design_id: designId,
        design_text: designSel.options[designSel.selectedIndex].text,
        size,
        quantity: qty,
        price
    });

    renderNewItems();
}

function renderNewItems() {
    const tbody = document.getElementById("new-body");
    tbody.innerHTML = "";
    newItems.forEach((item, idx) => {
        const line = item.quantity * item.price;
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${item.design_text}</td>
            <td>${item.size}</td>
            <td>${item.quantity}</td>
            <td>₹${item.price.toFixed(2)}</td>
            <td>₹${line.toFixed(2)}</td>
            <td><button type="button" onclick="removeNewItem(${idx})">❌</button></td>
        `;
        tbody.appendChild(tr);
    });
}

function removeNewItem(idx) {
    newItems.splice(idx, 1);
    renderNewItems();
}

function submitExchange() {
    resetMessage();
    if (!currentInvoice) {
        showMessage("Fetch an invoice first", true);
        return;
    }
    const payment = document.getElementById("return-payment").value;
    if (!payment) {
        showMessage("Select payment mode", true);
        return;
    }

    let items;
    try {
        items = collectReturnItems();
    } catch (err) {
        showMessage(err.message, true);
        return;
    }

    if (items.length === 0) {
        showMessage("Enter return quantities", true);
        return;
    }
    if (newItems.length === 0) {
        showMessage("Add new items for exchange", true);
        return;
    }

    fetch("/api/exchanges", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            invoice_no: currentInvoice.invoice_no,
            payment_mode: payment,
            return_items: items,
            new_items: newItems
        })
    })
    .then(r => r.json().then(data => ({ ok: r.ok, data })))
    .then(({ ok, data }) => {
        if (!ok) throw new Error(data.error || "Exchange failed");
        const settle = data.settlement;
        let settleText = "No payment needed";
        if (settle.type === "REFUND") settleText = `Refund ₹${settle.amount.toFixed(2)}`;
        if (settle.type === "COLLECT") settleText = `Collect ₹${settle.amount.toFixed(2)}`;
        showMessage(`Exchange done. Ref ${data.exchange_ref}. ${settleText}.`);
        newItems = [];
        renderNewItems();
        fetchInvoice();
    })
    .catch(err => showMessage(err.message, true));
}

function showMessage(msg, isError = false) {
    const el = document.getElementById("message");
    el.style.color = isError ? "#b00020" : "#0b7a0b";
    el.innerText = msg;
}

function resetMessage() {
    const el = document.getElementById("message");
    el.innerText = "";
}

// Size loader for new item dropdown
const designSelect = document.getElementById("new-design");
designSelect.addEventListener("change", () => {
    const designId = designSelect.value;
    const price = designSelect.options[designSelect.selectedIndex]?.dataset.price || "";
    document.getElementById("new-price").value = price;
    const sizeSel = document.getElementById("new-size");
    sizeSel.innerHTML = '<option value="">Select size</option>';
    if (!designId) return;
    fetch(`/get-sizes/${designId}`)
        .then(r => r.json())
        .then(data => {
            data.forEach(row => {
                const opt = document.createElement("option");
                opt.value = row.size;
                opt.textContent = row.size;
                sizeSel.appendChild(opt);
            });
        });
});
