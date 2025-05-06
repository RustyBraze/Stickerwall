
const ADMIN_TOKEN = localStorage.getItem('auth_token');
if (!ADMIN_TOKEN) {
    window.location.href = 'login.html';
}

// We need the host address to set the correct host address
const hostURL = window.location.origin;
console.log(hostURL);


// const ADMIN_TOKEN = "supersecrettoken"; // Same as server

async function fetchStickers() {
    // const response = await fetch("http://127.0.0.1:8000/api/stickers", {
    const hostEndpoint = hostURL + '/api/stickers';
    const response = await fetch(hostEndpoint, {
        headers: {
            Authorization: `Bearer ${ADMIN_TOKEN}`
        }
    });
    // const data = await response.json();
    // return data;
    return await response.json();
}

async function deleteSticker(id) {
    await fetch(`/stickers/${id}`, {
        method: 'DELETE',
        headers: {
            Authorization: `Bearer ${ADMIN_TOKEN}`
        }
    });
    location.reload();
}

function showStickerModal(sticker) {
    console.log(sticker);
    console.log('running showStickerModal');

    const modal = document.getElementById('stickerModal');
    const modalImage = document.getElementById('modalStickerImage');
    const modalUsers = document.getElementById('modalUserList');
    const modalStickerId = document.getElementById('modalStickerId');

    modalImage.src = sticker.file_path;
    modalStickerId.value = sticker.sticker_id;

    // Clear previous user list
    modalUsers.innerHTML = '';

    // Add users who sent this sticker
    sticker.users.forEach(user => {
        const userItem = document.createElement('div');
        userItem.className = 'list-group-item';
        userItem.innerHTML = `
            <div class="row align-items-center">
                <div class="col">
                    <div class="text-body">${user.telegram_user}</div>
                    <div class="text-muted">${user.telegram_id}</div>
                </div>
            </div>
        `;
        modalUsers.appendChild(userItem);
    });

    // Show the modal
    //<div class="modal modal-blur show" id="stickerModal" tabindex="-1" style="display: block;" aria-hidden="false" aria-modal="true">
    // modal.setAttribute('data-show', '');
    modal.classList.remove('fade');
    modal.classList.add('show');
    modal.style.display = 'block';
    modal.removeAttribute('aria-hidden');
    // modal.setAttribute('aria-hidden', 'false');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('role', 'dialog');

}

function hideStickerModal() {
    const modal = document.getElementById('stickerModal');

    // Restore original state
    //from this: <div class="modal modal-blur show" id="stickerModal" tabindex="-1" style="display: block;" aria-hidden="false" aria-modal="true">
    //  to this: <div class="modal modal-blur fade" id="stickerModal" tabindex="-1" style="display: none;"  aria-hidden="true">
    modal.removeAttribute('aria-modal');
    // modal.setAttribute('aria-hidden', 'true');
    modal.classList.remove('show');
    modal.classList.add('fade');
    modal.style.display = 'none';
}



document.addEventListener('DOMContentLoaded', function() {
    // Close button handler
    const closeButton = document.querySelector('#stickerModal .btn-close');
    if (closeButton) {
        closeButton.addEventListener('click', hideStickerModal);
    }

    // Click outside modal handler
    const modal = document.getElementById('stickerModal');
    modal.addEventListener('click', function(event) {
        // Check if click was on the modal backdrop (modal itself) and not its contents
        if (event.target === modal) {
            hideStickerModal();
        }
    });

    // Optional: ESC key handler
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape' && modal.classList.contains('show')) {
            hideStickerModal();
        }
    });
});



// Update the delete button handler
document.getElementById('deleteStickerBtn').addEventListener('click', async () => {
    const stickerId = document.getElementById('modalStickerId').value;
    if (confirm("Are you sure you want to delete this sticker?")) {
        await deleteSticker(stickerId);
        const modal = document.getElementById('stickerModal');
        modal.removeAttribute('data-show');
        await loadStickers();
    }
});



async function loadStickers() {
    // const stickers = await fetchStickers();
    // // Create the image holders
    // const stickerelement = document.getElementById("sticker_active");
    //
    // // stickerelement.innerHTML += '<img class="sticker" src="stickers/CAACAgEAAxkBAAIBQmgWZoYJBe8OUc_93BZ_ICoEj-C9AAKvAANPh-QI97ss0aHds4M2BA.webp" alt="Sticker">';
    // // document.body.appendChild(stickerelement);
    //
    // for (const id of stickers) {
    //     const img = document.createElement('img');
    //     img.className = 'sticker';
    //     img.src = id;
    //     img.alt = "Sticker";
    //     img.onclick = () => {
    //         if (confirm("Delete this sticker?")) {
    //             deleteSticker(id);
    //         }
    //     };
    //
    //     stickerelement.appendChild(img);
    //
    //
    //
    //     // const div = document.createElement('div');
    //     // div.className = 'sticker';
    //     // div.innerHTML = `<img src="${id}" alt="Sticker">`;
    //     // div.onclick = () => {
    //     //     if (confirm("Delete this sticker?")) {
    //     //         deleteSticker(id);
    //     //     }
    //     // };
    //     // document.body.appendChild(div);
    //
    // }


    // const response = await fetch("http://127.0.0.1:8000/api/admin/stickers", {
    //     headers: {
    //         Authorization: `Bearer ${ADMIN_TOKEN}`
    //     }
    // });
    // const stickers = await response.json();
    const stickers = await fetchStickers();

    // console.log(stickers);

    const activeContainer = document.getElementById("sticker_active");
    const inactiveContainer = document.getElementById("sticker_inactive");

    // Clear existing content
    activeContainer.innerHTML = '';
    inactiveContainer.innerHTML = '';

    // Group stickers by sticker_id
    const stickerGroups = {};
    stickers.forEach(sticker => {
        if (!stickerGroups[sticker.sticker_id]) {

            stickerGroups[sticker.sticker_id] = {
                sticker_id: sticker.sticker_id,
                file_path: sticker.file_path,
                enabled: sticker.enabled,
                users: []
            };

            const usergroup = sticker.telegram;

            usergroup.forEach(sticker_telegram => {
                stickerGroups[sticker.sticker_id].users.push({
                    telegram_user: sticker_telegram.user,
                    telegram_id: sticker_telegram.id
                });
            });
        }
    });
    // console.log(stickerGroups);

    // Create and append sticker elements
    Object.values(stickerGroups).forEach(stickerGroup => {
        const container = stickerGroup.enabled ? activeContainer : inactiveContainer;

        const img = document.createElement('img');
        img.className = 'sticker';
        img.src = stickerGroup.file_path;
        img.alt = "Sticker";
        img.onclick = () => showStickerModal(stickerGroup);

        container.appendChild(img);
    });

}

async function clearAll() {
    if (confirm("Are you sure you want to clear ALL stickers?")) {
        const stickers = await fetchStickers();
        for (const id of stickers) {
            await deleteSticker(id);
        }
        location.reload();
    }
}


function showTab(tab) {
    document.getElementById('stickersTab').style.display = (tab === 'stickers') ? 'block' : 'none';
    document.getElementById('configTab').style.display = (tab === 'config') ? 'block' : 'none';
}




loadStickers();
