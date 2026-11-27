const field = id => document.getElementById(id);
const option = (label, value) => new Option(label, value);
const accounts = messenger.accounts.list(true);

async function refreshStatus(result) {
  field("status").textContent = result || await messenger.runtime.sendMessage("status");
  const {history = []} = await messenger.storage.local.get("history");
  field("history").replaceChildren(...history.map(item => {
    const row = document.createElement("li");
    row.textContent = new Date(item.date).toLocaleString() + " · " + item.result;
    return row;
  }));
}

async function folders() {
  const account = (await accounts).find(item => item.id === field("account").value);
  field("folder").replaceChildren();
  function add(folder) {
    field("folder").add(option(folder.path, folder.id));
    for (const child of folder.subFolders || []) add(child);
  }
  for (const folder of account?.rootFolder?.subFolders || []) add(folder);
}

async function initialize() {
  const settings = await messenger.storage.local.get();
  for (const key of ["token", "from"]) field(key).value = settings[key] || "";
  if (!field("from").value) field("from").value = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);
  field("port").value = settings.port || 8000;
  field("automatic").checked = settings.automatic || false;
  for (const account of await accounts) {
    field("account").add(option(account.name, account.id));
    for (const identity of account.identities) field("identity").add(option(identity.email, identity.id));
  }
  if (settings.account) field("account").value = settings.account;
  await folders();
  field("folder").value = settings.folder || "";
  await refreshStatus();
}

field("account").onchange = folders;
field("settings").onsubmit = async event => {
  event.preventDefault();
  const settings = Object.fromEntries(["account", "folder", "from", "token", "port"].map(key => [key, field(key).value]));
  const previous = await messenger.storage.local.get();
  if (settings.folder !== previous.folder || settings.from !== previous.from || settings.port !== previous.port) settings.last = null;
  await messenger.storage.local.set({...settings, automatic: field("automatic").checked});
  await refreshStatus();
};
for (const action of ["sync"]) {
  field(action).onclick = async () => {
    field("status").textContent = "Synchronizing…";
    await refreshStatus(await messenger.runtime.sendMessage(action));
  };
}
field("compose").onsubmit = async event => {
  event.preventDefault();
  try {
    await messenger.compose.beginNew({
      identityId: field("identity").value, to: [field("recipient").value],
      subject: field("subject").value, plainTextBody: field("body").value, isPlainText: true,
    });
  } catch {
    field("status").textContent = "Thunderbird could not open the compose window.";
  }
};
initialize().catch(() => { field("status").textContent = "Could not load Thunderbird accounts."; });
