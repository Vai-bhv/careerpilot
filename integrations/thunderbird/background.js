let running = false;

async function request(path, settings, body) {
  const port = Number(settings.port || 8000);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error("Invalid API port");
  const response = await fetch("http://127.0.0.1:" + port + "/thunderbird" + path, {
    method: body ? "POST" : "GET",
    headers: {Authorization: "Bearer " + settings.token, "Content-Type": "application/json"},
    body: body ? JSON.stringify(body) : undefined,
    redirect: "error",
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error("CareerPilot HTTP " + response.status);
  return response.json();
}

function textParts(part, parts = []) {
  if (/^attachment\b/i.test(part.headers?.["content-disposition"]?.[0] || "") || part.name || part.contentType === "message/rfc822") return parts;
  if (["text/plain", "text/html"].includes(part.contentType) && part.body) parts.push(part);
  for (const child of part.parts || []) textParts(child, parts);
  return parts;
}

async function sync(settings, selected = null) {
  if (running) return "Synchronization already running";
  if (!settings.token || !settings.folder || !settings.from) throw new Error("Save a token, folder and start date first");
  running = true;
  let cursor = null;
  let count = 0;
  try {
    await request("/status", settings);
    const started = new Date().toISOString();
    let page;
    if (selected) {
      page = selected;
    } else {
      const from = settings.last
        ? new Date(Math.max(Date.parse(settings.from), Date.parse(settings.last) - 86400000))
        : new Date(settings.from);
      page = await messenger.messages.query({folderId: settings.folder, fromDate: from, toDate: new Date(started)});
    }
    do {
      cursor = page.id;
      for (const message of page.messages) {
        if (selected && message.folder?.id !== settings.folder) continue;
        if (!message.headerMessageId) continue;
        const parts = textParts(await messenger.messages.getFull(message.id));
        const part = parts.find(item => item.contentType === "text/html") || parts[0];
        if (!part) continue;
        const body = [...part.body].slice(0, 40000).join("");
        await request("/messages", settings, {
          message_id: "<" + message.headerMessageId.replace(/^<|>$/g, "") + ">",
          subject: (message.subject || "").slice(0, 500),
          sender: (message.author || "").slice(0, 1000),
          body,
          html: part.contentType === "text/html",
        });
        count++;
      }
      page = cursor ? await messenger.messages.continueList(cursor) : null;
    } while (page);
    cursor = null;
    if (!selected) {
      const current = await messenger.storage.local.get();
      if (["folder", "from", "token", "port"].every(key => current[key] === settings[key])) {
        await messenger.storage.local.set({last: started});
      }
    }
    return count + " messages processed (duplicates reused)";
  } finally {
    if (cursor) await messenger.messages.abortList(cursor).catch(() => {});
    running = false;
  }
}

async function execute(selected) {
  const settings = await messenger.storage.local.get();
  let result;
  try {
    result = await sync(settings, selected);
  } catch (error) {
    result = /^CareerPilot HTTP \d+$/.test(error.message) ? error.message : "Sync failed. Check the saved folder, pairing and local API.";
  }
  const history = [{date: new Date().toISOString(), result}, ...(settings.history || [])].slice(0, 20);
  await messenger.storage.local.set({history});
  return result;
}

messenger.action.onClicked.addListener(() => messenger.runtime.openOptionsPage());
messenger.alarms.create("careerpilot-sync", {periodInMinutes: 15});
messenger.alarms.onAlarm.addListener(async alarm => {
  const {automatic} = await messenger.storage.local.get("automatic");
  if (alarm.name === "careerpilot-sync" && automatic) await execute(null);
});
messenger.runtime.onMessage.addListener(async action => {
  if (action === "sync") return execute(null);
  if (action === "status") {
    const settings = await messenger.storage.local.get();
    if (!settings.token) return "Pairing required";
    try {
      await request("/status", settings);
      return "Paired";
    } catch {
      return "Disconnected or token revoked";
    }
  }
});

messenger.menus.create({id: "careerpilot-import", title: "Import selected recruitment messages", contexts: ["message_list"]});
messenger.menus.onClicked.addListener(info => {
  if (info.menuItemId === "careerpilot-import" && info.selectedMessages) return execute(info.selectedMessages);
});
