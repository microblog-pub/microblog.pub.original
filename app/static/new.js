// The new post textarea
var ta = document.getElementsByTagName("textarea")[0];
let simplemde = new SimpleMDE({
    element: ta,

});
// Helper for inserting text (emojis) in the textarea
function insertAtCursor (textToInsert) {
    ta.focus();
    const isSuccess = document.execCommand("insertText", false, textToInsert);

    // Firefox (non-standard method)
    if (!isSuccess) {
        // Credits to https://www.everythingfrontend.com/posts/insert-text-into-textarea-at-cursor-position.html
        // get current text of the input
        const value = ta.value;
        // save selection start and end position
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        // update the value with our text inserted
        ta.value = value.slice(0, start) + textToInsert + value.slice(end);
        // update cursor to be at the end of insertion
        ta.selectionStart = ta.selectionEnd = start + textToInsert.length;
    }
}
// Emoji click callback func
var ji = function (ev) {
    insertAtCursor(ev.target.attributes.alt.value + " ");
    ta.focus()
    //console.log(document.execCommand('insertText', false /*no UI*/, ev.target.attributes.alt.value));
}
// Enable the click for each emojis
var items = document.getElementsByClassName("ji")
for (var i = 0; i < items.length; i++) {
    items[i].addEventListener('click', ji);
}

// Add new input text dynamically to allow setting an alt text on attachments
var files = document.getElementById("files");
var alts = document.getElementById("alts");
if (files != null) {
    files.addEventListener("change", function(e) {
        // Reset the div content
        alts.innerHTML = "";

        // Add an input for each files
        for (var i = 0; i < e.target.files.length; i++) {
            var p = document.createElement("p");
            var altInput = document.createElement("input");
            altInput.setAttribute("type", "text");
            altInput.setAttribute("name", "alt_" + e.target.files[i].name);
            altInput.setAttribute("placeholder", "Alt text for " + e.target.files[i].name);
            altInput.setAttribute("style", "width:95%;")
            p.appendChild(altInput);
            alts.appendChild(p);
        }
    });
}
// Focus at the end of the textarea
ta.setSelectionRange(ta.value.length, ta.value.length);
ta.focus();


// Ctrl+Vで画像添付
document.addEventListener('paste', async (event) => {
    const items = event.clipboardData.items;
    const fileInput = document.getElementById('files');
    const dataTransfer = new DataTransfer();

    let previews = document.getElementById("files-preview");
    if (previews == null) {
        previews = document.createElement("div");
        previews.id = "files-preview";
        previews.style.display = "flex";
        previews.style.flexWrap = "wrap";
        previews.style.gap = "5px";
        fileInput.parentNode.appendChild(previews);
    }

    for (const existingFile of fileInput.files) {
        dataTransfer.items.add(existingFile);
    }

    var added = false;
    for (const item of items) {
        if (item.type.startsWith('image/')) {
            const file = item.getAsFile();
            if (!file) continue;
            added = true;

            dataTransfer.items.add(file);

            const preview = document.createElement('img');
            preview.style.maxWidth = '200px';
            preview.style.maxHeight = '200px';
            preview.style.objectFit = 'contain';
            preview.style.margin = "2px";
            const reader = new FileReader();
            reader.onload = (e) => {
                preview.src = e.target.result;
                previews.appendChild(preview);
            };
            reader.readAsDataURL(file);
        }
    }

    if (added) {
        fileInput.files = dataTransfer.files;
    }
});

// Ctrl+Enterで投稿
ta.addEventListener('keydown', function(event) {
    if (event.ctrlKey && event.key === 'Enter') {
        event.preventDefault();
        document.querySelector('.admin-new').submit();
    }
});
