"""任務路由 — 橫展任務 CRUD 與我的待辦"""
from flask import Blueprint, jsonify, request
from datetime import date
from ..services.task_service import TaskService
from ..utils import auth_required

task_bp = Blueprint('task', __name__)


@task_bp.route('/api/tasks', methods=['GET'])
@auth_required
def list_tasks(current_user):
    """GET /api/tasks — 任務列表，支援多維篩選"""
    try:
        result = TaskService.list_tasks(
            source_type  = request.args.get('source_type'),
            source_id    = int(request.args['source_id']) if request.args.get('source_id') else None,
            assignee_id  = int(request.args['assignee_id']) if request.args.get('assignee_id') else None,
            status       = request.args.get('status'),
            category     = request.args.get('category'),
            due_from     = date.fromisoformat(request.args['due_from']) if request.args.get('due_from') else None,
            due_to       = date.fromisoformat(request.args['due_to']) if request.args.get('due_to') else None,
            page         = int(request.args.get('page', 1)),
            per_page     = int(request.args.get('per_page', 20)),
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@task_bp.route('/api/tasks/my', methods=['GET'])
@auth_required
def my_tasks(current_user):
    """GET /api/tasks/my — 當前使用者的未完成待辦"""
    try:
        tasks = TaskService.my_tasks(assignee_id=current_user.id)
        return jsonify(tasks), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@task_bp.route('/api/tasks', methods=['POST'])
@auth_required
def create_task(current_user):
    """POST /api/tasks — 建立任務（一般用途，D7 有專屬路由）"""
    data = request.get_json() or {}
    required = ('source_type', 'source_id', 'category')
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'缺少必填欄位：{missing}'}), 400
    try:
        due = date.fromisoformat(data['due_date']) if data.get('due_date') else None
        task = TaskService.create(
            source_type  = data['source_type'],
            source_id    = int(data['source_id']),
            category     = data['category'],
            assignee_id  = data.get('assignee_id'),
            due_date     = due,
            description  = data.get('description'),
            part_nos     = data.get('part_nos'),
        )
        return jsonify(task), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@task_bp.route('/api/tasks/<int:task_id>/status', methods=['PATCH'])
@auth_required
def update_task_status(current_user, task_id: int):
    """PATCH /api/tasks/<id>/status — 狀態切換"""
    data = request.get_json() or {}
    new_status = data.get('status')
    if not new_status:
        return jsonify({'error': '缺少 status 欄位'}), 400
    try:
        task = TaskService.update_status(
            task_id=task_id,
            new_status=new_status,
            completion_proof=data.get('completion_proof'),
            waiver_reason=data.get('waiver_reason'),
        )
        return jsonify(task), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@task_bp.route('/api/tasks/<int:task_id>', methods=['DELETE'])
@auth_required
def delete_task(current_user, task_id: int):
    """DELETE /api/tasks/<id> — 僅 pending 狀態可刪"""
    try:
        TaskService.delete(task_id)
        return jsonify({'message': '刪除成功'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@task_bp.route('/api/tasks/check-gate', methods=['GET'])
@auth_required
def check_close_gate(current_user):
    """GET /api/tasks/check-gate?source_type=capa&source_id=1 — D8 結案前 gate 確認"""
    source_type = request.args.get('source_type')
    source_id   = request.args.get('source_id')
    if not source_type or not source_id:
        return jsonify({'error': '缺少 source_type 或 source_id'}), 400
    try:
        result = TaskService.check_close_gate(source_type, int(source_id))
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
