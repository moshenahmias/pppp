win:
	pyinstaller win.spec
	copy LICENSE dist
	copy assets\fonts\* dist\*

clean:
	rd /s /q dist