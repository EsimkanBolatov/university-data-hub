"""
Миграция для создания таблиц Skill Tree
alembic/versions/xxxx_skill_tree.py

Команды для применения:
alembic revision --autogenerate -m "add skill tree tables"
alembic upgrade head
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = 'skill_tree_001'
down_revision: Union[str, None] = '3eb12f42ef90'  # Предыдущая миграция
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создание таблиц Skill Tree"""
    
    # 1. Таблица навыков
    op.create_table(
        'skills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('is_global', sa.Boolean(), default=False),
        sa.Column('specialty_id', sa.Integer(), nullable=True),
        sa.Column('syllabus_source_file', sa.String(), nullable=True),
        sa.Column('level', sa.Integer(), default=1),
        sa.Column('estimated_hours', sa.Integer(), default=10),
        sa.Column('prerequisites_json', postgresql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['parent_id'], ['skills.id']),
        sa.ForeignKeyConstraint(['specialty_id'], ['professions.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_skills_id', 'skills', ['id'])
    op.create_index('ix_skills_name', 'skills', ['name'])
    op.create_index('ix_skills_is_global', 'skills', ['is_global'])
    
    # 2. Таблица материалов
    op.create_table(
        'skill_materials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('author_type', sa.String(), default='student'),
        sa.Column('type', sa.Enum('lecture', 'video', 'code_task', '3d_model', 'article', 'quiz', name='materialtype'), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('content', postgresql.JSON(), nullable=False),
        sa.Column('rating', sa.Integer(), default=0),
        sa.Column('views', sa.Integer(), default=0),
        sa.Column('status', sa.Enum('approved', 'pending_review', 'rejected', name='materialstatus'), default='pending_review'),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('review_comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=True),
        sa.Column('updated_at', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id']),
        sa.ForeignKeyConstraint(['author_id'], ['users.id']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_skill_materials_id', 'skill_materials', ['id'])
    op.create_index('ix_skill_materials_skill_id', 'skill_materials', ['skill_id'])
    op.create_index('ix_skill_materials_rating', 'skill_materials', ['rating'])
    
    # 3. Таблица челленджей
    op.create_table(
        'employer_challenges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.Column('employer_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('task_description', sa.Text(), nullable=False),
        sa.Column('requirements', postgresql.JSON(), nullable=True),
        sa.Column('verification_type', sa.Enum('ai_vision', 'manual_employer', 'auto_test', name='verificationtype'), nullable=False),
        sa.Column('ai_validation_prompt', sa.Text(), nullable=True),
        sa.Column('points', sa.Integer(), default=100),
        sa.Column('certificate_template', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('deadline', sa.String(), nullable=True),
        sa.Column('max_attempts', sa.Integer(), default=3),
        sa.Column('created_at', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id']),
        sa.ForeignKeyConstraint(['employer_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_employer_challenges_id', 'employer_challenges', ['id'])
    op.create_index('ix_employer_challenges_skill_id', 'employer_challenges', ['skill_id'])
    
    # 4. Таблица прогресса студентов
    op.create_table(
        'user_skill_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('locked', 'in_progress', 'verified', name='skillstatus'), default='locked'),
        sa.Column('progress_percentage', sa.Integer(), default=0),
        sa.Column('materials_completed', postgresql.JSON(), default=[]),
        sa.Column('proof_artifact', sa.String(), nullable=True),
        sa.Column('proof_metadata', postgresql.JSON(), nullable=True),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('verified_by', sa.Integer(), nullable=True),
        sa.Column('verification_comment', sa.Text(), nullable=True),
        sa.Column('started_at', sa.String(), nullable=True),
        sa.Column('completed_at', sa.String(), nullable=True),
        sa.Column('verified_at', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id']),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_skill_progress_id', 'user_skill_progress', ['id'])
    op.create_index('ix_user_skill_progress_user_id', 'user_skill_progress', ['user_id'])
    op.create_index('ix_user_skill_progress_skill_id', 'user_skill_progress', ['skill_id'])
    
    # 5. Таблица отправленных решений
    op.create_table(
        'challenge_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('challenge_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('submission_file', sa.String(), nullable=False),
        sa.Column('submission_metadata', postgresql.JSON(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), default='pending'),
        sa.Column('ai_check_result', postgresql.JSON(), nullable=True),
        sa.Column('manual_check_result', postgresql.JSON(), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('attempt_number', sa.Integer(), default=1),
        sa.Column('submitted_at', sa.String(), nullable=True),
        sa.Column('checked_at', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['challenge_id'], ['employer_challenges.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_challenge_submissions_id', 'challenge_submissions', ['id'])
    op.create_index('ix_challenge_submissions_user_id', 'challenge_submissions', ['user_id'])
    
    # 6. Таблица рейтингов материалов
    op.create_table(
        'material_ratings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('material_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['material_id'], ['skill_materials.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_material_ratings_id', 'material_ratings', ['id'])


def downgrade() -> None:
    """Удаление таблиц Skill Tree"""
    op.drop_index('ix_material_ratings_id', table_name='material_ratings')
    op.drop_table('material_ratings')
    
    op.drop_index('ix_challenge_submissions_user_id', table_name='challenge_submissions')
    op.drop_index('ix_challenge_submissions_id', table_name='challenge_submissions')
    op.drop_table('challenge_submissions')
    
    op.drop_index('ix_user_skill_progress_skill_id', table_name='user_skill_progress')
    op.drop_index('ix_user_skill_progress_user_id', table_name='user_skill_progress')
    op.drop_index('ix_user_skill_progress_id', table_name='user_skill_progress')
    op.drop_table('user_skill_progress')
    
    op.drop_index('ix_employer_challenges_skill_id', table_name='employer_challenges')
    op.drop_index('ix_employer_challenges_id', table_name='employer_challenges')
    op.drop_constraint('challenge_submissions_challenge_id_fkey', 'challenge_submissions', type_='foreignkey')
    op.drop_table('employer_challenges')
    
    op.drop_index('ix_skill_materials_rating', table_name='skill_materials')
    op.drop_index('ix_skill_materials_skill_id', table_name='skill_materials')
    op.drop_index('ix_skill_materials_id', table_name='skill_materials')
    op.drop_table('skill_materials')
    
    op.drop_index('ix_skills_is_global', table_name='skills')
    op.drop_index('ix_skills_name', table_name='skills')
    op.drop_index('ix_skills_id', table_name='skills')
    op.drop_table('skills')