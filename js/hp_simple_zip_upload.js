import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// 上传函数：复用 ComfyUI 的 /upload/image 接口，但我们自己控制参数
async function uploadZipToInput(file) {
	const form = new FormData();
	form.append("image", file, file.name); // 接口参数名必须是 image
	form.append("type", "input");
	form.append("overwrite", "true");
	
	const resp = await api.fetchApi("/upload/image", {
		method: "POST",
		body: form,
	});
	
	if (!resp.ok) {
		throw new Error(`Upload failed: ${resp.status} ${resp.statusText}`);
	}
	return await resp.json();
}

app.registerExtension({
	name: "HP.SimpleZipUpload",
	async beforeRegisterNodeDef(nodeType, nodeData) {
		// 仅针对 HPSimpleZipDecode 节点生效
		if (nodeData.name === "HPSimpleZipDecode") {
			const onNodeCreated = nodeType.prototype.onNodeCreated;
			
			nodeType.prototype.onNodeCreated = function () {
				if (onNodeCreated) onNodeCreated.apply(this, arguments);

				// 使用 setTimeout 确保节点初始化完成，防止找不到 widgets
				setTimeout(() => {
				const node = this;
				const zipWidget = node.widgets?.find((w) => w.name === "zip_file");
				
				// 如果没找到 zip_file 控件，就不处理
				if (!zipWidget) return;

				// 1. 创建隐藏的 HTML input 元素，专门用于选择 ZIP
				// 挂载在 node 对象上防止重复创建
				if (!node._hpZipInput) {
					const fileInput = document.createElement("input");
					fileInput.type = "file";
					fileInput.accept = ".zip,application/zip,application/x-zip-compressed"; // 仅允许 ZIP
					fileInput.style.display = "none";
					document.body.appendChild(fileInput);
					node._hpZipInput = fileInput;

					// 监听文件选择变化
					fileInput.onchange = async () => {
						try {
							const file = fileInput.files?.[0];
							if (!file) return;

							// 执行上传
							const res = await uploadZipToInput(file);
							
							// 拼接路径 (如果有子文件夹)
							const uploadedPath = res.subfolder ? `${res.subfolder}/${res.name}` : res.name;

							// 如果是下拉列表(Combo)，先添加选项
							if (zipWidget.options?.values) {
								if (!zipWidget.options.values.includes(uploadedPath)) {
									zipWidget.options.values.push(uploadedPath);
									zipWidget.options.values.sort();
								}
							}
							
							// 赋值 (无论是下拉还是文本框)
							zipWidget.value = uploadedPath;

							// 触发回调通知 ComfyUI 值变了
							if (zipWidget.callback) {
								zipWidget.callback(uploadedPath);
							}
							
							// 刷新画布
							app.graph.setDirtyCanvas(true, true);
                            console.log(`[HP-Zip] Uploaded: ${uploadedPath}`);

						} catch (e) {
							console.error("[HP-Zip] Upload failed:", e);
							alert("Upload failed: " + e.message);
						} finally {
							fileInput.value = ""; // 重置 input，确保下次选同名文件也能触发
						}
					};
				}

				// 2. 添加一个按钮控件到节点上
				// 检查是否已经存在（防止重载时重复添加）
				const uploadBtnName = "⬆️ Upload ZIP";
				const existingBtn = node.widgets?.find(w => w.name === uploadBtnName);
				
				if (!existingBtn) {
					node.addWidget("button", uploadBtnName, null, () => {
						// 点击按钮时，触发隐藏 input 的点击
						node._hpZipInput.click();
					});
				}
				}, 0);
			};
		}
	},
});
