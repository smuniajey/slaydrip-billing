// =====================================================
// SLAYDRIP POS SYSTEM - UNIFIED INTERFACE
// =====================================================

// =====================================================
// UTILITY FUNCTIONS
// =====================================================
function formatDate(dateString) {
    const date = new Date(dateString);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}.${month}.${year}`;
}

// =====================================================
// MODE MANAGEMENT
// =====================================================
let currentMode = 'sales';

function switchMode(mode) {
    currentMode = mode;
    
    // Update button states
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.mode === mode) {
            btn.classList.add('active');
        }
    });

    
    // Show/hide sections
    document.querySelectorAll('.mode-section').forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById(`${mode}-section`).classList.add('active');
    
    // Reset state for non-active modes
    if (mode !== 'return') {
        resetReturnMode();
    }
    // Ensure refund mode is hidden when entering Return section until data is fetched
    if (mode === 'return') {
        const refundField = document.getElementById('return-payment');
        if (refundField && refundField.parentElement) {
            refundField.parentElement.classList.add('hidden');
        }
    }
    if (mode !== 'exchange') {
        resetExchangeMode();
    }
    if (mode !== 'sales') {
        // Sales doesn't need reset as cart persists
    }
}

// =====================================================
// SALES MODE
// =====================================================
let cart = [];

function addToCart() {
    const designSelect = document.getElementById("design");
    const sizeSelect = document.getElementById("size");
    const quantityInput = document.getElementById("quantity");

    const selectedOption = designSelect.options[designSelect.selectedIndex];
    const designId = designSelect.value;
    const designText = selectedOption.text;
    const price = parseFloat(selectedOption.dataset.price);
    const size = sizeSelect.value;
    const quantity = parseInt(quantityInput.value);

    if (!designId || !size || !quantity || quantity <= 0) {
        alert("Please select design, size, and valid quantity");
        return;
    }

    cart.push({
        design_id: parseInt(designId),
        design_text: designText,
        size: size,
        quantity: quantity,
        price: price
    });

    renderCart();
}

function renderCart() {
    const tbody = document.getElementById("cart-body");
    const totalEl = document.getElementById("grand-total");

    tbody.innerHTML = "";
    let grandTotal = 0;

    cart.forEach((item, index) => {
        const rowTotal = item.quantity * item.price;
        grandTotal += rowTotal;

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${item.design_text}</td>
            <td>${item.size}</td>
            <td>
                <button type="button" onclick="decreaseQty(${index})">−</button>
                ${item.quantity}
                <button type="button" onclick="increaseQty(${index})">+</button>
            </td>
            <td>₹${item.price}</td>
            <td>₹${rowTotal}</td>
            <td>
                <button type="button" onclick="removeItem(${index})">❌</button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    totalEl.innerText = `₹${grandTotal}`;
}

function increaseQty(index) {
    cart[index].quantity++;
    renderCart();
}

function decreaseQty(index) {
    if (cart[index].quantity > 1) {
        cart[index].quantity--;
    }
    renderCart();
}

function removeItem(index) {
    cart.splice(index, 1);
    renderCart();
}

// Load sizes for sales mode
document.getElementById("design").addEventListener("change", function () {
    const designId = this.value;
    const sizeSelect = document.getElementById("size");

    sizeSelect.innerHTML = '<option value="">Select size</option>';
    if (!designId) return;

    fetch(`/get-sizes/${designId}`)
        .then(res => res.json())
        .then(data => {
            const sizeOrder = ['xxs', 'xs', 's', 'm', 'l', 'xl', 'xxl', 'xxxl'];
            data.sort((a, b) => {
                const aIndex = sizeOrder.indexOf(a.size.toLowerCase());
                const bIndex = sizeOrder.indexOf(b.size.toLowerCase());
                return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
            });
            
            data.forEach(row => {
                const opt = document.createElement("option");
                opt.value = row.size;
                const stock = Number(row.stock ?? 0);
                const label = stock > 0 ? `${row.size} (${stock} left)` : `${row.size} (Out of stock)`;
                opt.textContent = label;
                opt.disabled = stock <= 0;
                opt.dataset.stock = stock;
                sizeSelect.appendChild(opt);
            });
        })
        .catch(err => console.error("Size fetch error:", err));
});

function proceedToCheckout() {
    if (cart.length === 0) {
        alert("Cart is empty");
        return;
    }

    const customerName = document.getElementById("customer_name").value;
    const phone = document.getElementById("phone").value;
    const paymentMode = document.getElementById("payment_mode").value;

    if (!customerName || !phone || !paymentMode) {
        alert("Please fill all details");
        return;
    }

    fetch("/save-cart", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cart: cart })
    })
    .then(() => {
        const discount = document.getElementById("discount_percent").value || 0;
        const formData = new FormData();
        formData.append("customer_name", customerName);
        formData.append("phone", phone);
        formData.append("payment_mode", paymentMode);
        formData.append("discount_percent", discount);

        return fetch("/checkout", {
            method: "POST",
            body: formData
        });
    })
    .then(res => res.text())
    .then(html => {
        document.open();
        document.write(html);
        document.close();
    });
}

// =====================================================
// RETURN MODE
// =====================================================
let returnInvoice = null;
let returnSoldItems = [];

function fetchInvoiceForReturn() {
    const invoiceInput = document.getElementById("return_invoice_no");
    const inv = invoiceInput.value.trim();
    resetReturnMessage();
    
    if (!inv) {
        showReturnMessage("Enter invoice number", true);
        return;
    }

    fetch(`/api/invoice/${encodeURIComponent(inv)}`)
        .then(r => r.json().then(data => ({ ok: r.ok, data })))
        .then(({ ok, data }) => {
            if (!ok) {
                showReturnMessage(data.error || "Invoice not found", true);
                document.getElementById("return-invoice-summary").classList.add("hidden");
                document.getElementById("return-items-block").classList.add("hidden");
                const refundField = document.getElementById('return-payment');
                if (refundField && refundField.parentElement) {
                    refundField.parentElement.classList.add('hidden');
                }
                returnInvoice = null;
                return;
            }

            console.log('Invoice data:', data);
            console.log('Items:', data.items);
            
            returnInvoice = data.sale;
            returnSoldItems = data.items || [];
            
            console.log('returnSoldItems length:', returnSoldItems.length);
            
            renderReturnInvoiceSummary();
            renderReturnSoldItems();
        })
        .catch(err => {
            console.error('Fetch error:', err);
            showReturnMessage("Error fetching invoice", true);
        });
}

function renderReturnInvoiceSummary() {
    const s = returnInvoice;
    document.getElementById("return-invoice-summary").classList.remove("hidden");
    document.getElementById("return-items-block").classList.remove("hidden");
    const refundField = document.getElementById('return-payment');
    if (refundField && refundField.parentElement) {
        refundField.parentElement.classList.remove('hidden');
    }
    document.getElementById("return-sum-name").innerText = s.customer_name;
    document.getElementById("return-sum-phone").innerText = s.phone;
    document.getElementById("return-sum-invoice").innerText = s.invoice_no;
    document.getElementById("return-sum-date").innerText = s.bill_date ? formatDate(s.bill_date) : "";
    document.getElementById("return-sum-mode").innerText = s.payment_mode;
}

function renderReturnSoldItems() {
    const tbody = document.getElementById("return-sold-body");
    console.log('Rendering items, tbody:', tbody);
    console.log('Items to render:', returnSoldItems);
    
    if (!tbody) {
        console.error('Table body not found!');
        return;
    }
    
    tbody.innerHTML = "";
    
    if (returnSoldItems.length === 0) {
        const tr = document.createElement("tr");
        tr.innerHTML = '<td colspan="6" style="text-align:center; padding:20px; color:#999;">No items found in this invoice</td>';
        tbody.appendChild(tr);
        return;
    }
    
    returnSoldItems.forEach((item, idx) => {
        console.log('Rendering item:', item);
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${item.design_code} | ${item.product_name} | ${item.color}</td>
            <td>${item.size}</td>
            <td>${item.sold_qty}</td>
            <td>${item.already_returned}</td>
            <td>${item.returnable}</td>
            <td><input type="number" min="0" max="${item.returnable}" value="0" data-idx="${idx}" class="return-input"></td>
        `;
        tbody.appendChild(tr);
    });
    
    console.log('Rendered', returnSoldItems.length, 'items');
}

function collectReturnItems() {
    const inputs = document.querySelectorAll(".return-input");
    const items = [];
    inputs.forEach(input => {
        const qty = parseInt(input.value || 0, 10);
        if (qty > 0) {
            const item = returnSoldItems[parseInt(input.dataset.idx, 10)];
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
    resetReturnMessage();
    if (!returnInvoice) {
        showReturnMessage("Fetch an invoice first", true);
        return;
    }
    const payment = document.getElementById("return-payment").value;
    if (!payment) {
        showReturnMessage("Select payment mode", true);
        return;
    }

    let items;
    try {
        items = collectReturnItems();
    } catch (err) {
        showReturnMessage(err.message, true);
        return;
    }

    if (items.length === 0) {
        showReturnMessage("Enter return quantities", true);
        return;
    }

    fetch("/api/returns", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            invoice_no: returnInvoice.invoice_no,
            payment_mode: payment,
            items
        })
    })
    .then(r => r.json().then(data => ({ ok: r.ok, data })))
    .then(({ ok, data }) => {
        if (!ok) throw new Error(data.error || "Return failed");
        showReturnMessage(`✅ RETURN SUCCESSFUL!\n\nReference: ${data.return_ref}\nRefund Amount: ₹${data.total_refund.toFixed(2)}\nPayment Mode: ${payment}`);
        
        // Clear inputs after 3 seconds
        setTimeout(() => {
            resetReturnMode();
        }, 3000);
    })
    .catch(err => showReturnMessage(err.message, true));
}

function showReturnMessage(msg, isError = false) {
    const el = document.getElementById("return-message");
    el.style.color = isError ? "#b00020" : "#0b7a0b";
    el.innerText = msg;
}

function resetReturnMessage() {
    document.getElementById("return-message").innerText = "";
}

function resetReturnMode() {
    document.getElementById("return_invoice_no").value = "";
    document.getElementById("return-invoice-summary").classList.add("hidden");
    document.getElementById("return-items-block").classList.add("hidden");
    document.getElementById("return-payment").value = "";
    const refundField = document.getElementById('return-payment');
    if (refundField && refundField.parentElement) {
        refundField.parentElement.classList.add('hidden');
    }
    resetReturnMessage();
    returnInvoice = null;
    returnSoldItems = [];
}

// =====================================================
// EXCHANGE MODE
// =====================================================
let exchangeInvoice = null;
let exchangeSoldItems = [];
let exchangeNewItems = [];

// Calculate and display exchange settlement (global scope)
function calculateExchangeSettlement() {
    const settlementSummary = document.getElementById("exchange-settlement-summary");
    const paymentSection = document.getElementById("exchange-payment-section");

    // If no invoice is loaded, keep summary hidden and exit
    if (!exchangeInvoice) {
        settlementSummary.classList.add("hidden");
        return;
    }

    // Calculate returned value and update line totals
    const inputs = document.querySelectorAll(".exchange-return-input");
    let returnedTotal = 0;
    inputs.forEach(input => {
        const idx = parseInt(input.dataset.idx, 10);
        const qty = parseInt(input.value || 0, 10);
        const item = exchangeSoldItems[idx];
        const lineTotal = item.unit_price * qty;
        returnedTotal += lineTotal;
        
        // Update line total display
        const lineTotalCell = document.querySelector(`.line-total-${idx}`);
        if (lineTotalCell) {
            lineTotalCell.innerText = `₹${lineTotal.toFixed(2)}`;
        }
    
        // Update returned total display
        const returnedTotalEl = document.getElementById("exchange-returned-total");
        if (returnedTotalEl) {
            returnedTotalEl.innerText = `₹${returnedTotal.toFixed(2)}`;
        }
    });

    // Calculate new items value
    let newTotal = 0;
    exchangeNewItems.forEach(item => {
        newTotal += item.price * item.quantity;
    });

    // Default discount comes from template, but keep editable
    const discountInput = document.getElementById("exchange-discount");
    const discountPercent = parseFloat(discountInput?.value || 0);
    const discountAmount = (newTotal * discountPercent) / 100;
    const newTotalAfterDiscount = newTotal - discountAmount;

    // Calculate difference
    const difference = returnedTotal - newTotalAfterDiscount;

    // Update UI
    document.getElementById("settlement-returned-value").innerText = `₹${returnedTotal.toFixed(2)}`;
    document.getElementById("settlement-new-value").innerText = `₹${newTotal.toFixed(2)}`;
    document.getElementById("settlement-discount").innerText = `-₹${discountAmount.toFixed(2)}`;

    const settlementType = document.getElementById("settlement-type");
    const settlementAmount = document.getElementById("settlement-amount");

    if (exchangeNewItems.length > 0) {
        settlementSummary.classList.remove("hidden");

        if (Math.abs(difference) < 0.01) {
            // Even exchange
            settlementType.innerText = "EVEN EXCHANGE";
            settlementAmount.innerText = "₹0.00";
            settlementAmount.style.color = "#000";
            paymentSection.classList.add("hidden");
        } else if (difference > 0) {
            // Refund to customer
            settlementType.innerText = "REFUND TO CUSTOMER";
            settlementAmount.innerText = `₹${difference.toFixed(2)}`;
            settlementAmount.style.color = "#d32f2f";
            paymentSection.classList.remove("hidden");
        } else {
            // Collect from customer
            settlementType.innerText = "COLLECT FROM CUSTOMER";
            settlementAmount.innerText = `₹${Math.abs(difference).toFixed(2)}`;
            settlementAmount.style.color = "#388e3c";
            paymentSection.classList.remove("hidden");
        }
    } else {
        settlementSummary.classList.add("hidden");
        paymentSection.classList.remove("hidden");
    }
}

function fetchInvoiceForExchange() {
    const invoiceInput = document.getElementById("exchange_invoice_no");
    const inv = invoiceInput.value.trim();
    resetExchangeMessage();
    document.getElementById("exchange-settlement-summary").classList.add("hidden");
    
    if (!inv) {
        showExchangeMessage("Enter invoice number", true);
        return;
    }

    fetch(`/api/invoice/${encodeURIComponent(inv)}`)
        .then(r => r.json().then(data => ({ ok: r.ok, data })))
        .then(({ ok, data }) => {
            if (!ok) {
                showExchangeMessage(data.error || "Invoice not found", true);
                document.getElementById("exchange-invoice-summary").classList.add("hidden");
                document.getElementById("exchange-items-block").classList.add("hidden");
                document.getElementById("exchange-new-block").classList.add("hidden");
                document.getElementById("exchange-discount-field").classList.add("hidden");
                document.getElementById("exchange-settlement-summary").classList.add("hidden");
                exchangeInvoice = null;
                return;
            }

            exchangeInvoice = data.sale;
            exchangeSoldItems = data.items || [];
            resetExchangeMessage();
            renderExchangeInvoiceSummary();
            renderExchangeSoldItems();
            document.getElementById("exchange-new-block").classList.remove("hidden");
            document.getElementById("exchange-discount-field").classList.remove("hidden");
            document.getElementById("exchange-payment-section").classList.remove("hidden");
        })
        .catch(() => {
            showExchangeMessage("Error fetching invoice", true);
            document.getElementById("exchange-discount-field").classList.add("hidden");
            document.getElementById("exchange-settlement-summary").classList.add("hidden");
            document.getElementById("exchange-payment-section").classList.add("hidden");
        });
}

function renderExchangeInvoiceSummary() {
    const s = exchangeInvoice;
    document.getElementById("exchange-invoice-summary").classList.remove("hidden");
    document.getElementById("exchange-items-block").classList.remove("hidden");
    document.getElementById("exchange-sum-name").innerText = s.customer_name;
    document.getElementById("exchange-sum-phone").innerText = s.phone;
    document.getElementById("exchange-sum-invoice").innerText = s.invoice_no;
    document.getElementById("exchange-sum-date").innerText = s.bill_date ? formatDate(s.bill_date) : "";
    document.getElementById("exchange-sum-mode").innerText = s.payment_mode;
}

function renderExchangeSoldItems() {
    const tbody = document.getElementById("exchange-sold-body");
    console.log('Exchange: Rendering items, tbody:', tbody);
    console.log('Exchange: Items to render:', exchangeSoldItems);
    
    if (!tbody) {
        console.error('Exchange table body not found!');
        return;
    }
    
    tbody.innerHTML = "";
    
    if (exchangeSoldItems.length === 0) {
        const tr = document.createElement("tr");
        tr.innerHTML = '<td colspan="8" style="text-align:center; padding:20px; color:#999;">No items found in this invoice</td>';
        tbody.appendChild(tr);
        return;
    }
    
    exchangeSoldItems.forEach((item, idx) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${item.design_code} | ${item.product_name} | ${item.color}</td>
            <td>${item.size}</td>
            <td>${item.sold_qty}</td>
            <td>${item.already_returned}</td>
            <td>${item.returnable}</td>
            <td>₹${item.unit_price.toFixed(2)}</td>
            <td><input type="number" min="0" max="${item.returnable}" value="0" data-idx="${idx}" class="exchange-return-input" oninput="calculateExchangeSettlement()"></td>
            <td class="line-total-${idx}">₹${item.unit_price.toFixed(2)}</td>
        `;
        tbody.appendChild(tr);
    });
    calculateExchangeSettlement();
}

function collectExchangeReturnItems() {
    const inputs = document.querySelectorAll(".exchange-return-input");
    const items = [];
    inputs.forEach(input => {
        const qty = parseInt(input.value || 0, 10);
        if (qty > 0) {
            const item = exchangeSoldItems[parseInt(input.dataset.idx, 10)];
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

function addExchangeNewItem() {
    resetExchangeMessage();
    const designSel = document.getElementById("exchange-new-design");
    const sizeSel = document.getElementById("exchange-new-size");
    const qtyInput = document.getElementById("exchange-new-qty");
    const priceInput = document.getElementById("exchange-new-price");

    const designId = parseInt(designSel.value || 0, 10);
    const size = sizeSel.value;
    const qty = parseInt(qtyInput.value || 0, 10);
    const price = parseFloat(priceInput.value || 0);

    if (!designId || !size || qty <= 0) {
        showExchangeMessage("Select design, size and qty", true);
        return;
    }
    if (Number.isNaN(price)) {
        showExchangeMessage("Price missing for design", true);
        return;
    }

    exchangeNewItems.push({
        design_id: designId,
        design_text: designSel.options[designSel.selectedIndex].text,
        size,
        quantity: qty,
        price
    });

    renderExchangeNewItems();
}

function renderExchangeNewItems() {
    const tbody = document.getElementById("exchange-new-body");
    tbody.innerHTML = "";
    exchangeNewItems.forEach((item, idx) => {
        const line = item.quantity * item.price;
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${item.design_text}</td>
            <td>${item.size}</td>
            <td>${item.quantity}</td>
            <td>₹${item.price.toFixed(2)}</td>
            <td>₹${line.toFixed(2)}</td>
            <td><button type="button" onclick="removeExchangeNewItem(${idx})">❌</button></td>
        `;
        tbody.appendChild(tr);
    });
    calculateExchangeSettlement();
}

function removeExchangeNewItem(idx) {
    exchangeNewItems.splice(idx, 1);
    renderExchangeNewItems();
}

// Load sizes for exchange new item dropdown
document.getElementById("exchange-new-design").addEventListener("change", function() {
    const designId = this.value;
    const price = this.options[this.selectedIndex]?.dataset.price || "";
    document.getElementById("exchange-new-price").value = price;
    const sizeSel = document.getElementById("exchange-new-size");
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

function submitExchange() {
    resetExchangeMessage();
    if (!exchangeInvoice) {
        showExchangeMessage("Fetch an invoice first", true);
        return;
    }
    
    // Check if payment is needed
    const paymentSection = document.getElementById("exchange-payment-section");
    let payment = "";
    
    if (!paymentSection.classList.contains("hidden")) {
        payment = document.getElementById("exchange-payment").value;
        if (!payment) {
            showExchangeMessage("Select payment mode", true);
            return;
        }
    } else {
        // Even exchange, no payment needed
        payment = "None";
    }

    let items;
    try {
        items = collectExchangeReturnItems();
    } catch (err) {
        showExchangeMessage(err.message, true);
        return;
    }

    if (items.length === 0) {
        showExchangeMessage("Enter return quantities", true);
        return;
    }
    if (exchangeNewItems.length === 0) {
        showExchangeMessage("Add new items for exchange", true);
        return;
    }

    const discountPercent = parseFloat(document.getElementById("exchange-discount").value || 0);

    fetch("/api/exchanges", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            invoice_no: exchangeInvoice.invoice_no,
            payment_mode: payment,
            return_items: items,
            new_items: exchangeNewItems,
            discount_percent: discountPercent
        })
    })
    .then(r => r.json().then(data => ({ ok: r.ok, data })))
    .then(({ ok, data }) => {
        if (!ok) throw new Error(data.error || "Exchange failed");
        const settle = data.settlement;
        let settleText = "No payment adjustment needed";
        if (settle.type === "REFUND") settleText = `Refund to Customer: ₹${settle.amount.toFixed(2)}`;
        if (settle.type === "COLLECT") settleText = `Collect from Customer: ₹${settle.amount.toFixed(2)}`;
        showExchangeMessage(`✅ EXCHANGE SUCCESSFUL!\n\nReference: ${data.exchange_ref}\n${settleText}\nPayment Mode: ${payment}`);
        
        // Clear inputs after 3 seconds
        setTimeout(() => {
            resetExchangeMode();
        }, 3000);
    })
    .catch(err => showExchangeMessage(err.message, true));
}

function showExchangeMessage(msg, isError = false) {
    const el = document.getElementById("exchange-message");
    el.style.color = isError ? "#b00020" : "#0b7a0b";
    el.innerText = msg;
}

function resetExchangeMessage() {
    document.getElementById("exchange-message").innerText = "";
}

function resetExchangeMode() {
    document.getElementById("exchange_invoice_no").value = "";
    document.getElementById("exchange-invoice-summary").classList.add("hidden");
    document.getElementById("exchange-items-block").classList.add("hidden");
    document.getElementById("exchange-new-block").classList.add("hidden");
    document.getElementById("exchange-discount-field").classList.add("hidden");
    document.getElementById("exchange-payment-section").classList.add("hidden");
    document.getElementById("exchange-settlement-summary").classList.add("hidden");
    document.getElementById("exchange-payment").value = "";
    resetExchangeMessage();
    exchangeInvoice = null;
    exchangeSoldItems = [];
    exchangeNewItems = [];
    renderExchangeNewItems();
}
