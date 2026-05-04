
    let currentRow = null;

    function addRow() {
        const table = document.getElementById("routeTable");
        const tr = document.createElement("tr");
        const rules = ["全体承認", "グループ承認"]

        tr.innerHTML = `
          <td>
            <div>
            <button type="button" onclick="addRow()">+</button>
            <button type="button" onclick="deleteRow(this)">-</button>
            <span class="ordered">${table.rows.length + 1}</span>
            </div> 
            <div>
              <select name="rule[]" id="ruleType">
                  ${rules.map(item => `<option value="${item}">${item}</option>`).join("")}
              </select>
            </div>
          </td>
          <td>
          <button type="button" onclick="openModal(this)">編集</button>
            <table class="subtable"></table>
            <input type="hidden" name="members[]" class="selected-members">
          </td>
        `;

        table.appendChild(tr);
    }

    function deleteRow(button) {

        const table = document.getElementById("routeTable");
        if (table.rows.length <= 1) return;

        const tr = button.closest("tr")

        tr.remove();
        updateRowOrdered();
    }

    function updateRowOrdered() {
        const table = document.getElementById("routeTable");
        const rows = table.children;

        Array.from(rows).forEach((row, index) => {
            console.log(index);
            const cell = row.querySelector(".ordered");
            if (cell) {
                cell.textContent = index + 1;

            }
        });
    }

    function closeModal() {
        document.getElementById("modalOverlay").style.display = "none";
        currentRow = null;
  }


  function openModal(button) {
        currentRow = button.closest("tr");

        const hidden = currentRow.querySelector(".selected-members");
        const savedMembers = hidden.value ? JSON.parse(hidden.value) : [];
        const savedIds = savedMembers.map(m => String(m.id))
        const checkboxes = document.querySelectorAll('#modalOverlay input[name="modal_member"]');
        checkboxes.forEach(cb => {
            cb.checked = savedIds.includes(cb.value);
        })

        document.getElementById("modalOverlay").style.display = "block";
    }

    function applyModalValue() {
        if (!currentRow) return;

        const checkedBoxes = document.querySelectorAll('#modalOverlay input[name="modal_member"]:checked')
        const selectedMembers = Array.from(checkedBoxes).map(cb => ({
            id: cb.value,
            label: cb.dataset.label
        }));

        const subtable = currentRow.querySelector(".subtable");
        renderSubtable(subtable, selectedMembers);

        currentRow.querySelector(".selected-members").value = JSON.stringify(selectedMembers);

        closeModal();
        console.log(selectedMembers);
    }

    function renderSubtable(subtable, members) {

        subtable.innerHTML = "";

        const tr = document.createElement("tr");

        members.forEach(member => {
            const td = document.createElement("td");
            td.textContent = member.label;
            td.dataset.id = member.id;
            tr.appendChild(td);
        });

        subtable.appendChild(tr);
    }
