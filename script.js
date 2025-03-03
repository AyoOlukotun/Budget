document.addEventListener("DOMContentLoaded", () => {
    const bankSelect = document.getElementById("bank-select");
    const reauthLinkDiv = document.getElementById("reauthentication-link");

    const yearSelect = document.getElementById("year-select");
    const currentYear = new Date().getFullYear();

    // Check if the dropdown exists
    if (!yearSelect) {
        console.error("Year dropdown element not found.");
        return;
    }

    // Populate year options (e.g., last 5 years to next year)
    for (let year = currentYear - 5; year <= currentYear + 1; year++) {
        const option = document.createElement("option");
        option.value = year;
        option.textContent = year; // Display year as text
        if (year === currentYear) {
            option.selected = true; // Set the current year as selected
        }
        yearSelect.appendChild(option);
    }

    // Initial fetch for the current year
    updateTables(currentYear);

    // Event listener to handle dropdown change
    yearSelect.addEventListener("change", () => {
        const selectedYear = yearSelect.value;
        updateTables(selectedYear);
    });



    function updateTables(year) {
        fetch(`/api/grouped-expenditure?year=${year}`)
            .then(response => response.json())
            .then(data => populateGroupedExpenditureTable(data))
            .catch(error => console.error("Error fetching grouped expenditure:", error));

        fetch(`/api/breakdown-by-bank?year=${year}`)
            .then(response => response.json())
            .then(data => populateBreakdownByBankTable(data))
            .catch(error => console.error("Error fetching breakdown by bank:", error));
    }

    function populateGroupedExpenditureTable(data) {
        const tableBody = document.getElementById("grouped-expenditure-table").querySelector("tbody");
        tableBody.innerHTML = "";
        data.forEach(row => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${row.classification}</td>
                ${generateMonthCells(row, "classification")}
                <td>${row.Total || 0}</td>
            `;
            tableBody.appendChild(tr);
        });
    }

    function populateBreakdownByBankTable(data) {
        const tableBody = document.getElementById("breakdown-by-bank-table").querySelector("tbody");
        tableBody.innerHTML = "";
        data.forEach(row => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${row.bank}</td>
                <td>${row.classification}</td>
                ${generateMonthCells(row, "classification")}
                <td>${row.Total || 0}</td>
            `;
            tableBody.appendChild(tr);
        });
    }

    function generateMonthCells(row, categoryField) {
        const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        return months.map((month, idx) => `
            <td data-category="${row[categoryField]}" data-month="${idx + 1}" class="clickable-cell">
                ${row[month] || 0}
            </td>
        `).join("");
    }

    // Handle re-authentication button
    document.getElementById("reauthenticate-button").addEventListener("click", () => {
        const selectedBank = bankSelect.value;

        if (!selectedBank) {
            alert("Please select a bank to start the re-authentication process.");
            return;
        }

        fetch(`/api/reauthenticate?bank=${encodeURIComponent(selectedBank)}`)
            .then(response => {
                if (!response.ok) throw new Error("Failed to generate re-authentication link.");
                return response.json();
            })
            .then(data => {
                if (data.link) {
                    reauthLinkDiv.innerHTML = `
                        <p>Re-authentication link for <strong>${selectedBank}</strong>:</p>
                        <a href="${data.link}" target="_blank">${data.link}</a>
                    `;
                } else {
                    reauthLinkDiv.innerHTML = `<p>Error: No link returned by the server.</p>`;
                }
            })
            .catch(error => {
                console.error("Error during re-authentication:", error);
                reauthLinkDiv.innerHTML = `<p>Error: Unable to generate the re-authentication link.</p>`;
            });
    });

    // Handle clickable cells for transaction details
    document.getElementById("grouped-expenditure-table").addEventListener("click", event => {
        const cell = event.target;
        if (cell.classList.contains("clickable-cell")) {
            const category = cell.dataset.category;
            const month = cell.dataset.month;
            fetchTransactionDetails(category, month);
        }
    });

    function fetchTransactionDetails(category, month) {
        fetch(`/api/transaction-details?category=${encodeURIComponent(category)}&month=${month}`)
            .then(response => response.json())
            .then(data => showTransactionPopup(data))
            .catch(error => console.error("Error fetching transaction details:", error));
    }

    function showTransactionPopup(transactions) {
        const overlay = document.getElementById("popup-overlay");
        const popup = document.getElementById("transaction-popup");
        const tableBody = document.getElementById("transaction-details-table").querySelector("tbody");

        tableBody.innerHTML = ""; // Clear existing content
        transactions.forEach(transaction => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${transaction.bookingDateTime || "N/A"}</td>
                <td>${transaction.bank || "N/A"}</td>
                <td>${transaction.transaction_description || "N/A"}</td>
                <td>${transaction.amount || 0}</td>
                <td>
                    <button class="update-category-btn" data-id="${transaction.id}" data-category="${transaction.classification}">
                        Update
                    </button>
                </td>
            `;
            tableBody.appendChild(tr);
        });

        document.querySelectorAll(".update-category-btn").forEach(button => {
            button.addEventListener("click", event => {
                const transactionId = event.target.dataset.id;
                const currentCategory = event.target.dataset.category;
                showCategoryUpdatePopup(transactionId, currentCategory);
            });
        });

        overlay.style.display = "block";
        popup.style.display = "block";

        document.getElementById("close-popup").addEventListener("click", () => {
            overlay.style.display = "none";
            popup.style.display = "none";
        });
    }

    function showCategoryUpdatePopup(transactionId, currentCategory) {
        const overlay = document.getElementById("popup-overlay");
        const categoryPopup = document.getElementById("category-update-popup");
        const categoryDropdown = document.getElementById("category-select-dropdown");

        categoryDropdown.innerHTML = "";
        const categories = ["Transport", "Groceries & Supermarkets", "Dining & Takeaways", "Retail & Shopping", "Entertainment", "Miscellaneous", "Income", "Household", "Exclude"];
        categories.forEach(category => {
            const option = document.createElement("option");
            option.value = category;
            option.textContent = category;
            if (category === currentCategory) option.selected = true;
            categoryDropdown.appendChild(option);
        });

        overlay.style.display = "block";
        categoryPopup.style.display = "block";

        document.getElementById("confirm-category-update").onclick = () => {
            const newCategory = categoryDropdown.value;
            updateTransactionCategory(transactionId, newCategory);

                // Close the pop-up after confirming
                document.getElementById('category-update-popup').style.display = 'none';
                document.getElementById('popup-overlay').style.display = 'none';
        };

        document.getElementById("cancel-category-update").onclick = () => {
            categoryPopup.style.display = "none";
            overlay.style.display = "none";
        };
    }

    function updateTransactionCategory(transactionId, newCategory) {
        fetch("/api/update-category", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ transaction_id: transactionId, new_category: newCategory })
        })
            .then(response => response.json())
            .then(data => {
                console.log(data.message);
                refreshGroupedExpenditure();
            })
            .catch(error => console.error("Error updating category:", error));
    }

    function refreshGroupedExpenditure() {
        fetch(`/api/grouped-expenditure?year=${yearSelect.value}`)
            .then(response => response.json())
            .then(data => populateGroupedExpenditureTable(data))
            .catch(error => console.error("Error refreshing grouped expenditure:", error));
    }
});
