import sys
import math
import networkx as nx

from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QRadioButton,
    QGraphicsView, QGraphicsScene, QButtonGroup,
    QMessageBox, QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsLineItem
)
from PyQt5.QtGui import (
    QPen, QBrush, QFont, QPainter, QPainterPath
)
from PyQt5.QtCore import (
    Qt, QPointF
)
from PyQt5.QtWidgets import QGraphicsItem

# --------------------------------------------------------------------------------
# EdgeItem 클래스 : 두 NodeItem 사이의 간선을 시각화
# --------------------------------------------------------------------------------
class EdgeItem(QGraphicsLineItem):
    def __init__(self, node1, node2, weight=None, directed=False):
        super().__init__()
        self.node1 = node1
        self.node2 = node2
        self.weight = weight
        self.directed = directed

        # 간선 선 스타일
        self.setPen(QPen(Qt.black, 5))
        self.setZValue(0)  # 간선은 정점 아래에 표시

        # 가중치 표시 텍스트(있다면)
        if self.weight is not None:
            self.weight_text = QGraphicsTextItem(str(self.weight))
            self.weight_text.setFont(QFont("Arial", 10))
            self.weight_text.setZValue(0)
        else:
            self.weight_text = None

        self.updatePosition()

    def updatePosition(self):
        p1 = self.node1.pos()
        p2 = self.node2.pos()

        r = self.node1.radius
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        dist = math.hypot(dx, dy)
        if dist == 0:
            dist = 1

        dx /= dist
        dy /= dist

        # 간선이 NodeItem의 경계에서 시작/끝 나도록 조정
        start_x = p1.x() + dx * r
        start_y = p1.y() + dy * r
        end_x = p2.x() - dx * r
        end_y = p2.y() - dy * r

        self.setLine(start_x, start_y, end_x, end_y)

        # 가중치 텍스트 위치
        if self.weight_text is not None:
            mx = (start_x + end_x) / 2
            my = (start_y + end_y) / 2
            angle = math.atan2(end_y - start_y, end_x - start_x)
            offset = 15
            offset_x = -offset * math.sin(angle)
            offset_y = offset * math.cos(angle)

            text_x = mx + offset_x
            text_y = my + offset_y

            br = self.weight_text.boundingRect()
            self.weight_text.setPos(text_x - br.width()/2, text_y - br.height()/2)

    def addToScene(self, scene):
        scene.addItem(self)
        if self.weight_text:
            scene.addItem(self.weight_text)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)

        # 방향 그래프라면 화살표
        if self.directed:
            line = self.line()
            angle = math.atan2(-line.dy(), line.dx())
            arrow_size = 10
            arrow_angle = math.pi / 6  # 30도

            end_x = line.x2()
            end_y = line.y2()

            arrow_p1 = QPointF(
                end_x - arrow_size * math.cos(angle - arrow_angle),
                end_y + arrow_size * math.sin(angle - arrow_angle)
            )
            arrow_p2 = QPointF(
                end_x - arrow_size * math.cos(angle + arrow_angle),
                end_y + arrow_size * math.sin(angle + arrow_angle)
            )

            arrow_path = QPainterPath()
            arrow_path.moveTo(end_x, end_y)
            arrow_path.lineTo(arrow_p1)
            arrow_path.lineTo(arrow_p2)
            arrow_path.closeSubpath()

            painter.setBrush(Qt.black)
            painter.drawPath(arrow_path)

# --------------------------------------------------------------------------------
# NodeItem 클래스
# --------------------------------------------------------------------------------
class NodeItem(QGraphicsEllipseItem):
    def __init__(self, graph_editor, node_id, x, y, r=20):
        super().__init__(-r, -r, 2*r, 2*r)
        self.graph_editor = graph_editor
        self.node_id = node_id
        self.radius = r

        self.setPen(QPen(Qt.black, 2))
        self.setBrush(QBrush(Qt.lightGray))

        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setZValue(1)

        self.text_item = QGraphicsTextItem(str(node_id), self)
        self.text_item.setFont(QFont("Arial", 10))
        br = self.text_item.boundingRect()
        self.text_item.setPos(-br.width()/2, -br.height()/2)

        self.setPos(x, y)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.graph_editor.updateEdges(self.node_id)
        return super().itemChange(change, value)

# --------------------------------------------------------------------------------
# GraphEditor 클래스
# --------------------------------------------------------------------------------
class GraphEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Graph Editor")
        self.scale_factor = 1.0

        self.nodeItems = {}
        self.edgeItems = []

        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        self.setLayout(main_layout)

        # 왼쪽 패널
        left_layout = QVBoxLayout()
        main_layout.addLayout(left_layout, stretch=1)

        self.label_graph_type = QLabel("Select Graph Types:")
        self.radio_undirected = QRadioButton("non-directed graph")
        self.radio_directed = QRadioButton("directed graph")
        self.radio_undirected.setChecked(True)

        self.graph_type_group = QButtonGroup()
        self.graph_type_group.addButton(self.radio_undirected)
        self.graph_type_group.addButton(self.radio_directed)

        self.label_vertex = QLabel("nodes:")
        self.edit_vertex = QLineEdit()
        self.edit_vertex.setPlaceholderText("ex: 5")

        self.label_edges = QLabel("edges:")
        self.edit_edges = QTextEdit()
        self.edit_edges.setPlaceholderText("1 2\n2 3 10\n4 5 ...")

        self.btn_draw = QPushButton("draw graph")
        self.btn_draw.clicked.connect(self.draw_graph)

        self.btn_zoom_in = QPushButton("zoom in (+)")
        self.btn_zoom_in.clicked.connect(self.zoom_in)

        self.btn_zoom_out = QPushButton("zoom out (-)")
        self.btn_zoom_out.clicked.connect(self.zoom_out)

        self.btn_reset = QPushButton("Reset View")
        self.btn_reset.clicked.connect(self.reset_view)

        left_layout.addWidget(self.label_graph_type)
        left_layout.addWidget(self.radio_undirected)
        left_layout.addWidget(self.radio_directed)
        left_layout.addSpacing(10)
        left_layout.addWidget(self.label_vertex)
        left_layout.addWidget(self.edit_vertex)
        left_layout.addWidget(self.label_edges)
        left_layout.addWidget(self.edit_edges)
        left_layout.addWidget(self.btn_draw)
        left_layout.addSpacing(20)
        left_layout.addWidget(self.btn_zoom_in)
        left_layout.addWidget(self.btn_zoom_out)
        left_layout.addWidget(self.btn_reset)
        left_layout.addStretch()

        # 오른쪽 씬+뷰
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.setRenderHint(QPainter.Antialiasing, True)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)

        main_layout.addWidget(self.view, stretch=3)
        self.resize(2500, 1500)

    def draw_graph(self):
        self.scene.clear()
        self.nodeItems.clear()
        self.edgeItems.clear()

        directed = self.radio_directed.isChecked()

        # 정점 수
        try:
            vertex_count = int(self.edit_vertex.text().strip())
            if vertex_count <= 0:
                raise ValueError
        except ValueError:
            self.show_error("nodes are must be a positive integer.")
            return

        # 간선 정보 파싱
        edges_text = self.edit_edges.toPlainText().strip()
        if not edges_text:
            self.show_error("edges are required.")
            return

        lines = edges_text.splitlines()
        try:
            edges = self.parse_edges(lines)
        except Exception as e:
            self.show_error(f"Error parsing edges: {e}")
            return

        # 범위 검사
        for (a, b, w) in edges:
            if a < 1 or a > vertex_count or b < 1 or b > vertex_count:
                self.show_error(f"Node ID must be in range 1 to {vertex_count}.")
                return

        # 그래프 생성
        if directed:
            G = nx.DiGraph()
        else:
            G = nx.Graph()

        G.add_nodes_from(range(1, vertex_count + 1))
        for (a, b, w) in edges:
            if w is not None:
                G.add_edge(a, b, weight=w)
            else:
                G.add_edge(a, b)

        # --------------------------
        # 1) 연결 성분 구하기
        # --------------------------
        if directed:
            # G는 DiGraph 이므로 이건 OK
            components = list(nx.weakly_connected_components(G))
            # 레이아웃용 그래프 (무향 변환해서 spring_layout)
            layout_graph = G.to_undirected()
        else:
            # G는 Graph이므로
            components = list(nx.connected_components(G))
            layout_graph = G

        # --------------------------
        # 2) spring_layout에 쓸 파라미터
        # --------------------------
        if vertex_count <= 50:
            k = 0.3
            iterations = 100
        elif vertex_count <= 100:
            k = 0.15
            iterations = 150
        else:
            k = 0.05
            iterations = 200

        # --------------------------
        # 3) 연결 성분별로 레이아웃 계산 + 오프셋 배치
        # --------------------------
        pos = {}
        offset_x = 0.0

        for comp in components:
            # comp는 이 연결 성분에 속한 노드들의 set
            # 레이아웃용 서브그래프 (무향)
            subgraph_layout = layout_graph.subgraph(comp)

            # subgraph_layout에 대해 spring_layout
            sub_pos = nx.spring_layout(
                subgraph_layout,
                k=k,
                iterations=iterations,
                seed=42
            )

            # x축 오프셋 적용
            for node in sub_pos:
                px, py = sub_pos[node]
                pos[node] = (px + offset_x, py)

            # 다음 연결 성분은 x축으로 조금 더 밀어서 배치
            offset_x += 2.5

        # --------------------------
        # 4) NodeItem / EdgeItem 생성
        # --------------------------
        for node_id in G.nodes:
            x, y = pos[node_id]
            # 적당히 scale
            sx = x * 600
            sy = y * 600

            n_item = NodeItem(self, node_id, sx, sy, r=30)
            self.nodeItems[node_id] = n_item
            self.scene.addItem(n_item)

        for (a, b) in G.edges():
            w = G[a][b].get('weight', None)
            edge_item = EdgeItem(
                self.nodeItems[a],
                self.nodeItems[b],
                weight=w,
                directed=directed
            )
            edge_item.addToScene(self.scene)
            self.edgeItems.append(edge_item)

        # 뷰 맞춤
        self.view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        self.scale_factor = 1.0

    def parse_edges(self, lines):
        edges = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            toks = line.split()
            if len(toks) == 2:
                a, b = toks
                edges.append((int(a), int(b), None))
            elif len(toks) == 3:
                a, b, w = toks
                edges.append((int(a), int(b), float(w)))
            else:
                raise ValueError("Invalid edge format")
        return edges

    def show_error(self, msg):
        QMessageBox.critical(self, "Error", msg)

    def updateEdges(self, node_id):
        for edge in self.edgeItems:
            if edge.node1.node_id == node_id or edge.node2.node_id == node_id:
                edge.updatePosition()

    def zoom_in(self):
        self.scale_factor *= 1.2
        self.view.scale(1.2, 1.2)

    def zoom_out(self):
        self.scale_factor /= 1.2
        self.view.scale(1/1.2, 1/1.2)

    def reset_view(self):
        self.view.resetTransform()
        self.scale_factor = 1.0
        self.view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

def main():
    app = QApplication(sys.argv)
    editor = GraphEditor()
    editor.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
