// ==================================================
// SLAYDRIP BILLING SYSTEM – CART & CHECKOUT LOGIC
// ==================================================

// This array holds all cart items temporarily (frontend only)
let cart = [];

// ==================================================
// ADD ITEM TO CART
// ==================================================
function addToCart() {

    // Get form elements
    const designSelect = document.getElementById("design");
    const sizeSelect = document.getElementById("size");
    const quantityInput = document.getElementById("quantity");

    // Get selected design option
    const selectedOption = designSelect.options[designSelect.selectedIndex];

    // Extract values
    const designId = designSelect.value;
    const designText = selectedOption.text;           // Visible text in dropdown
    const price = parseFloat(selectedOption.dataset.price);
    const size = sizeSelect.value;
    const quantity = parseInt(quantityInput.value);

    // Validation check
    if (!designId || !size || !quantity || quantity <= 0) {
        alert("Please select design, size, and valid quantity");
        return;
    }

    // Push item into cart array
    cart.push({
        design_id: parseInt(designId),
        design_text: designText,
        size: size,
        quantity: quantity,
        price: price
    });

    // Re-render cart table
    renderCart();
}

// ==================================================
// RENDER CART TABLE
// ==================================================
function renderCart() {

    const tbody = document.getElementById("cart-body");
    const totalEl = document.getElementById("grand-total");

    // Clear existing rows
    tbody.innerHTML = "";

    let grandTotal = 0;

    // Loop through cart items
    cart.forEach((item, index) => {

        const rowTotal = item.quantity * item.price;
        grandTotal += rowTotal;

        // Create table row
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

    // Update total amount
    totalEl.innerText = `₹${grandTotal}`;
}

// ==================================================
// QUANTITY CONTROLS
// ==================================================
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

// ==================================================
// REMOVE ITEM FROM CART
// ==================================================
function removeItem(index) {
    cart.splice(index, 1);
    renderCart();
}

// ==================================================
// LOAD AVAILABLE SIZES WHEN DESIGN CHANGES
// ==================================================
document.getElementById("design").addEventListener("change", function () {

    const designId = this.value;
    const sizeSelect = document.getElementById("size");

    // Reset size dropdown
    sizeSelect.innerHTML = '<option value="">Select size</option>';

    // If no design selected, stop
    if (!designId) return;

    // Fetch sizes from Flask backend
    fetch(`/get-sizes/${designId}`)
        .then(res => res.json())
        .then(data => {
            data.forEach(row => {
                const opt = document.createElement("option");
                opt.value = row.size;
                opt.textContent = row.size;
                sizeSelect.appendChild(opt);
            });
        })
        .catch(err => console.error("Size fetch error:", err));
});

// ==================================================
// CHECKOUT PROCESS
// ==================================================
function proceedToCheckout() {

    // Cart empty check
    if (cart.length === 0) {
        alert("Cart is empty");
        return;
    }

    // Get customer details
    const customerName = document.getElementById("customer_name").value;
    const phone = document.getElementById("phone").value;
    const paymentMode = document.getElementById("payment_mode").value;

    // Validation
    if (!customerName || !phone || !paymentMode) {
        alert("Please fill all details");
        return;
    }

    // Step 1: Save cart into Flask session
    fetch("/save-cart", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cart: cart })
    })

    // Step 2: Submit checkout form
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

    // Step 3: Replace page with bill HTML
    .then(res => res.text())
    .then(html => {
        document.open();
        document.write(html);
        document.close();
    });
}
